"""
Usage:
    hackcmu [--blacklist=<bl>] <sub> <filename>
"""

from PyQt5.QtWidgets import (QWidget, QToolTip, QGridLayout, QHBoxLayout,
                             QPushButton, QApplication, QMessageBox)
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QWidget, QSlider, QTextEdit,
    QLabel, QApplication)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QPushButton, QAction, QLineEdit, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot

from random import randint
from bisect import bisect_left

import sys
import srt
import mpv
import nltk
import locale
import pdb
from docopt import docopt

class Communicate(QObject):
    delay_quiz = pyqtSignal()
    quiz = pyqtSignal()

class Example(QWidget):
    def __init__(self, filename, sub, blacklist):
        super().__init__()

        self.blacklist = blacklist

        self.correct = []
        self.incorrect = []
        self.line = ''
        self.finished = False

        with open(sub) as f:
            self.subs = list(srt.parse(f.read()))

        self.initUI()
        self.initVideo(filename, sub)

    def initUI(self):
        self.sub_text = QTextEdit(self, readOnly=True)
        self.sub_text.setCurrentFont(QFont('SansSerif', 20))

        self.toggle_play = QPushButton('Pause', self)
        self.toggle_play.clicked.connect(self.togglePlay)

        skip = QPushButton('Skip', self)

        submit = QPushButton('Submit', self)
        submit.clicked.connect(self.submit)

        self.seek = QSlider(Qt.Horizontal, self)
        self.seek.setFocusPolicy(Qt.NoFocus)

        self.guess = QLineEdit(self)
        self.guess.returnPressed.connect(self.submit)

        controls = QHBoxLayout()
        controls.setStretch(0, 2)
        controls.setStretch(1, 2)
        controls.setStretch(2, 6)
        controls.addWidget(self.toggle_play)
        controls.addWidget(skip)
        controls.addWidget(self.seek)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(self.sub_text, 0, 0, 2, 4)
        grid.addWidget(self.guess, 2, 0, 1, 3)
        grid.addWidget(submit, 2, 3, 1, 1)
        grid.addLayout(controls, 3, 0, 1, 4)

        self.c = Communicate()
        self.c.quiz.connect(self.quiz)
        self.c.delay_quiz.connect(self.delay_quiz)

        self.setLayout(grid)
        self.setWindowTitle('HackCMU')
        self.setGeometry(200, 200, 600, 400)
        self.show()

    def initVideo(self, filename, sub):
        locale.setlocale(locale.LC_NUMERIC, 'C')
        self.player = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True, geometry="55%", sub_scale=0)
        self.player.play(filename)
        self.player.sub_add(sub)

        @self.player.property_observer('sub-text')
        def subtitle_change(_name, text):
            if text:
                new_line = ' '.join([x.strip() for x in text.split('\n')])
                if self.line != new_line:
                    self.line = new_line
                    self.c.delay_quiz.emit()

        @self.player.property_observer('playback-time')
        def time_change(_name, new_time):
            self.duration = round(self.player.duration or self.duration)
            self.now = round(new_time or self.now)
            self.seek.setTickInterval(self.duration)
            self.seek.setValue(self.now)

            if not self.finished and abs(self.now - self.duration) < 2:
                self.finished = True
                QMessageBox.information(self, 'Message', 'Correct: {0}\nIncorrect: {1}'.format(len(self.correct), len(self.incorrect)))

    def currentSub(self):
        ctime = self.player.playback_time

        for sub in self.subs:
            if sub.start.total_seconds() < ctime < sub.end.total_seconds():
                return sub

    def delay_quiz(self):
        time = self.till_sub_end()
        if time:
            QTimer.singleShot(time, self.c.quiz)

    def till_sub_end(self):
        sub = self.currentSub()
        if sub:
            return round((sub.end.total_seconds() - self.player.playback_time) * 1000)
        else:
            return None

    def quiz(self):
        till_end = self.till_sub_end()
        if not till_end:
            pass
        elif till_end > 600:
            self.c.delay_quiz.emit()
        else:
            if randint(1,1) == 1:
                self.pause()
                tokens = nltk.word_tokenize(self.line)
                # Don't quiz on a line shorter than 3 tokens
                if len(tokens) > 2:
                    self.blank = choose_blank(tokens, self.blacklist)
                    if self.blank:
                        self.sub_text.setPlainText(self.line.replace(self.blank, '_'*len(self.blank)))
                    else:
                        self.sub_text.setPlainText(self.line)
            else:
                self.sub_text.setPlainText(self.line)

    def togglePlay(self):
        if self.player.pause:
            self.play()
        else:
            self.pause()

    def play(self):
        self.player.pause = False
        self.toggle_play.setText('Pause')
    
    def pause(self):
        self.player.pause = True
        self.toggle_play.setText('Play')

    def submit(self):
        if loose_eq(self.blank, self.guess.text()):
            self.correct.append(self.blank)
            QMessageBox.information(self, 'Message', 'Correct!')
        else:
            self.incorrect.append(self.blank)
            QMessageBox.information(self, 'Message', "No, the word was {0}.".format(self.blank))
        self.guess.clear()
        self.sub_text.setPlainText(self.line)
        self.play()

    def closeEvent(self, event):
        print("Correct:")
        for word in self.correct:
            print(word)

        print("Incorrect:")
        for word in self.incorrect:
            print(word)

        event.accept()


def loose_eq(word, guess):
    return word.strip().lower() == guess.strip().lower()

def choose_blank(tokens, blacklist, tries=10):
    if tries == 0:
        return None
    else:
        blank_idx = randint(0, len(tokens) - 1)
        blank = tokens[blank_idx]
        if len(blank) < 3 or blank.lower() in blacklist:
            return choose_blank(tokens, blacklist, tries=tries - 1)
        else:
            return blank


if __name__ == '__main__':
    app = QApplication([sys.argv[0]])
    args = docopt(__doc__, version='0.1')

    blacklist = []
    if args['--blacklist']:
        with open(args['--blacklist']) as f:
            for line in f:
                blacklist.append(line.strip().lower())

    ex = Example(args['<filename>'], args['<sub>'], blacklist)
    code = app.exec_()


    sys.exit(code)

