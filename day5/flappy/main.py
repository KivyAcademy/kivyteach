# -*- coding: utf-8 -*-
from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image
from kivy.uix.widget import Widget
from kivy.properties import ObjectProperty, ListProperty, NumericProperty, StringProperty
from kivy.properties import AliasProperty
from kivy.core.window import Window, Keyboard
from kivy.uix.label import Label
from kivy.uix.image import Image as ImageWidget
from kivy.core.audio import SoundLoader
#legg til her
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.storage.jsonstore import JsonStore


sfx_flap = SoundLoader.load("audio/flap.wav")
sfx_score = SoundLoader.load("audio/score.wav")
sfx_die = SoundLoader.load("audio/die.wav")
sfx_start = SoundLoader.load("audio/start.wav")

import random


class BaseWidget(Widget):
    def load_tileable(self, name):
        t = Image('images/{}.png'.format(name)).texture
        t.wrap = 'repeat'
        setattr(self, 'tx_{}'.format(name), t)


class Background(BaseWidget):
    tx_background = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(Background, self).__init__(**kwargs)
        self.load_tileable('background')

    def set_background_size(self, tx):
        tx.uvsize = (self.width / tx.width, -1)

    def on_size(self, *args):
        self.set_background_size(self.tx_background)

    def update(self, nap):
        self.set_background_uv('tx_background', 2 * nap)

    def set_background_uv(self, name, val):
        t = getattr(self, name)
        t.uvpos = ((t.uvpos[0] + val) % self.width, t.uvpos[1])
        self.property(name).dispatch(self)


class Pipe(BaseWidget):
    FLOOR = 96
    PTOP_HEIGHT = 26
    PIPE_GAP = 150

    tx_pipe = ObjectProperty(None)
    tx_ptop = ObjectProperty(None)

    ratio = NumericProperty(0.5)
    lower_len = NumericProperty(0)
    lower_coords = ListProperty((0, 0, 1, 0, 1, 1, 0, 1))
    upper_len = NumericProperty(0)
    upper_coords = ListProperty((0, 0, 1, 0, 1, 1, 0, 1))

    upper_y = AliasProperty(
            lambda self: self.height - self.upper_len,
            None, bind=['height', 'upper_len'])

    def __init__(self, **kwargs):
        super(Pipe, self).__init__(**kwargs)
        self.scored = False

        for name in ('pipe', 'ptop'):
            self.load_tileable(name)

    def set_coords(self, coords, len):
        len /= 16
        coords[5:] = (len, 0, len)

    def on_size(self, *args):
        pipes_length = self.height - (
                Pipe.FLOOR + Pipe.PIPE_GAP + 2 * Pipe.PTOP_HEIGHT)
        self.lower_len = self.ratio * pipes_length
        self.upper_len = pipes_length - self.lower_len
        self.set_coords(self.lower_coords, self.lower_len)
        self.set_coords(self.upper_coords, self.upper_len)
        self.bind(ratio=self.on_size)


class Bird(ImageWidget):

    ACCEL_FALL = 0.25
    ACCEL_JUMP = 5

    speed = NumericProperty(0)
    angle = AliasProperty(
            lambda self: 5 * self.speed,
            None, bind=['speed'])

    def gravity_on(self, height):

        self.pos_hint.pop('center_y', None)
        self.center_y = 0.6 * height

    def update(self, nap):
        self.speed -= Bird.ACCEL_FALL
        self.y += self.speed

    def bump(self):
        self.speed = Bird.ACCEL_JUMP


class ScoreLabel(Label):
    pass


class StartScreen(Screen):
    pass


class GameScreen(Screen):

    def on_enter(self):
        self.ids.background.update(1.0/60)


class KivyBirdRoot(FloatLayout):
    pass


class KivyBirdApp(App):

    pipes = []
    playing = False
    score = 0
    scored = False
    highscore = StringProperty("0")

    #legg til her
    def build(self):
        self.highscorestore = JsonStore("highscore.json")
        if self.highscorestore.exists("highscore"):
            print self.highscorestore.get("highscore")["score"]
            self.highscore = self.highscorestore.get("highscore")["score"]
        return KivyBirdRoot()

    # Når ting går over til ScreenManager, må du huske å bytte root.ids til screenen sin ID
    # Dette gjøres gjennom root.ids.kivybird_screen_manager.get_screen("game_screen")
    def on_start(self):
        self.spacing = 0.5 * self.root.width
        self.background = self.root.ids.kivybird_screen_manager.get_screen("game_screen").ids.background
        self.score_label = ScoreLabel()
        self.bird = self.root.ids.kivybird_screen_manager.get_screen("game_screen").ids.bird
        Clock.schedule_interval(self.update, 1.0/60.0)
        Window.bind(on_key_down=self.on_key_down)
        self.background.on_touch_down = self.user_action
        sfx_start.play()
        self.background.update(1.0 / 60.0)

    def on_key_down(self, window, key, *args):
        if key == Keyboard.keycodes['spacebar']:
            self.user_action()

    def user_action(self, *args):
        if not self.playing:
            sfx_start.play()
            self.bird.gravity_on(self.root.height)
            self.spawn_pipes()
            self.root.ids.kivybird_screen_manager.get_screen("game_screen").ids.score_label.text = "0"
            self.score = 0
            self.playing = True
        sfx_flap.play()
        self.bird.bump()

    def update(self, nap):
        if not self.playing:
            return
        self.background.update(nap)
        self.bird.update(nap)

        for p in self.pipes:
            p.x -= 96 * nap
            if p.x <= -64:
                p.x += 4 * self.spacing
                p.ratio = random.uniform(0.25, 0.75)
                p.scored = False

        if self.test_game_over():
            current_score = self.root.ids.kivybird_screen_manager.get_screen("game_screen").ids.score_label.text
            #self.highscorestore["highscore"] = {"score": current_score}
            if int(current_score) > int(self.highscore):
                self.highscore = current_score
                self.highscorestore.put("highscore", score=current_score)
            sfx_die.play()
            self.playing = False

    def test_game_over(self):

        screen_height = self.root.height

        if self.bird.y < 90 or self.bird.y > screen_height - 50:
            return True

        for p in self.pipes:
            if not p.collide_widget(self.bird):
                continue

            if (self.bird.y < p.lower_len + 116 or
                    self.bird.y > screen_height - (p.upper_len + 75)):
                return True
            if not p.scored and p.x < self.bird.x:
                p.scored = True
                sfx_score.play()
                self.score += 1
                self.root.ids.kivybird_screen_manager.get_screen("game_screen").ids.score_label.text = str(self.score)

        return False

    def spawn_pipes(self):
        for p in self.pipes:
            self.root.remove_widget(p)

        self.pipes = []

        for i in range(4):
            p = Pipe(x=self.root.width + (self.spacing * i))
            p.ratio = random.uniform(0.25, 0.75)
            self.root.add_widget(p)
            self.pipes.append(p)

if __name__ == "__main__":
    KivyBirdApp().run()
