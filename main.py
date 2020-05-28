import cv2
import youtube_dl
import skimage.metrics
import os
from pathlib import Path
from tkinter import *
from tkinter import filedialog
import tkinter.messagebox
from PIL import Image, ImageTk
import threading
import collections
import re
import shutil
import platform
import numpy as np

# Если в пятерке кадров разница между любыми 2 кадрами меньше заданного, считаем, что на глаз
# разница между всеми ними не слишком заметна и не ищем в такой последовательности 25 кадр
K1 = 100

# Если у пары последовательных кадров разница меньше заданного, считаем,
# что это один кадр повторяется несколько раз и не добавляем очередной кадр в очередь
K2 = 10

# Максимальное число одинаковых кадров подряд,
# если их больше, не считаем их одинаковыми и продолжаем добавление в очередь
K3 = 3

# К какому размеру масштабировать кадры перед анализом
size_x = 100
size_y = 100

IMG_N = 1
IMG1 = []
IMG2 = []
urls = {}
process_state = 0
frames_queue = collections.deque()
resized_queue = collections.deque()
frame_time = collections.deque()

if platform.system() == 'Windows':
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)


def frame_time_str(ms):
    ms = int(ms)
    s = int((ms / 1000) % 60)
    m = int((ms / (1000 * 60)) % 60)
    h = int(ms / (1000 * 60 * 60))
    return str(int(h)).zfill(2) + '_' + str(int(m)).zfill(2) + '_' + str(int(s)).zfill(2) + '_' + str(
        int(ms) % 1000).zfill(3)

def check25(frames):
    # 0 1 [2] 3 4
    c1_3 = skimage.metrics.mean_squared_error(frames[1], frames[3])
    c0_1 = skimage.metrics.mean_squared_error(frames[0], frames[1])
    c1_2 = skimage.metrics.mean_squared_error(frames[1], frames[2])
    c2_3 = skimage.metrics.mean_squared_error(frames[2], frames[3])
    c3_4 = skimage.metrics.mean_squared_error(frames[3], frames[4])
    m = max(c0_1, c1_2, c2_3, c3_4)
    if c1_2 > c1_3 and c2_3 > c1_3 and min(c1_2, c2_3) > max(c0_1, c3_4) and (m == c1_2 or m == c2_3) and m > K1:
        print(frame_time_str(frame_time[2]))
        print(c0_1,c1_2,c2_3,c3_4,c1_3)
        return True
    return False


def get_url_type(s):
    # Проверка, что это ссылка на youtube
    if re.match('https?://.*youtube.*watch?v=', s) or re.match('https?://youtu.be/.*', s):
        return get_video_url(s)

    # Если начинается на http, то это может быть прямая ссылка на видео
    elif len(s) > 5 and s[:4] == 'http':
        return s
    else:
        # Иначе это может быть путь к файлу
        print(s)
        try:
            fp = open(s, 'r')
            if fp:
                fp.close()
                l2.configure(text='')
                return s
        except:
            update_img(255 * np.ones(shape=[1, 1, 3], dtype=np.uint8))
    return


def get_video_url(url):
    global urls
    l2.configure(text="Загрузка информации о видео")
    if urls.get(url) and urls.get(url) != '*':
        return urls.get(url)
    try:
        ydl = youtube_dl.YoutubeDL({'outtmpl': '%(id)s%(ext)s'})
        with ydl:
            result = ydl.extract_info(url, download=False)

        if 'entries' in result:
            video = result['entries'][0]
        else:
            video = result

        for f in video['formats']:
            video_url = f['url']
            c = f['vcodec']
            if f['format_note'] == '360p' and c[:3] == 'avc':
                l2.configure(text='')
                urls[url] = video_url
                e2.delete(0, END)
                e2.insert(0, str(Path(os.getcwd(), result['id'])))
                return video_url
        l2.configure(text='')
    except:
        urls[url] = '*'
        update_img(255 * np.ones(shape=[1, 1, 3], dtype=np.uint8))
        return None


def save_img(img, imgfile, filepath, folder=None):
    if folder and not os.path.isdir(folder):
        try:
            os.mkdir(folder)
        except:
            print('Не удалось создать папку', folder)
    # OpenCV не поддерживает юникод в именах файлов в imwrite(), поэтому записывать во временную папку, а потом перемещение
    if platform.system() == 'Windows':
        tmpfile = 'c:\\windows\\temp\\' + imgfile
        try:
            cv2.imwrite(tmpfile, img)
        except:
            print('Не удалось записать файл', tmpfile)
        try:
            shutil.move(tmpfile, filepath)
        except:
            print('Не удалось переместить файл из', tmpfile, "в", filepath)
    else:
        try:
            cv2.imwrite(filepath, img)
        except:
            print('Не удалось записать файл', filepath)


def th_process():
    t2 = threading.Thread(target=process, args=())
    t2.start()


def process():
    frames_count = 0
    global frames_queue
    global resized_queue
    global frame_time
    global process_state
    b2.configure(text="ОТМЕНА")
    process_state += 1
    if process_state > 1:
        return
    try:
        os.mkdir(e2.get())
    except:
        print('Не удалось создать папку', e2.get())

    try:
        os.mkdir(Path(e2.get(), "1"))
    except:
        print('Не удалось создать папку', Path(e2.get(), "1"))

    try:
        os.mkdir(Path(e2.get(), "5"))
    except:
        print('Не удалось создать папку', Path(e2.get(), "5"))

    z = 0   #счетчик одинаковых кадров

    src = get_url_type(e1.get())
    if src:
        cap = cv2.VideoCapture(src)
        while process_state == 1 and cap.isOpened():
            cv2.waitKey(1)
            ret, frame = cap.read()
            if not ret:
                break
            update_img(resiz(frame))
            frame_resized = cv2.resize(frame, (size_x, size_y))

            if z < K3 and len(resized_queue) >= 1 and skimage.metrics.mean_squared_error(frame_resized,resized_queue[-1]) < K2:
                z += 1
                continue
            else:
                z = 0

            if len(frame_time) == 5:
                frame_time.popleft()
                frames_queue.popleft()
                resized_queue.popleft()
            frame_time.append(cap.get(cv2.CAP_PROP_POS_MSEC))
            frames_queue.append(frame)
            resized_queue.append(frame_resized)

            if len(frames_queue) == 5 and check25(resized_queue):
                frames_count+=1
                for i in range(len(frames_queue)):
                    imgfile = str(frame_time_str(frame_time[i]) + '.jpg')
                    filepath = Path(e2.get(), "5", frame_time_str(frame_time[2]), imgfile)
                    folder = Path(e2.get(), "5", frame_time_str(frame_time[2]))
                    save_img(frames_queue[i], imgfile, filepath, folder)

                imgfile = str(frame_time_str(frame_time[2]) + '.jpg')
                filepath = Path(e2.get(), "1", imgfile)
                save_img(frames_queue[2], imgfile, filepath)
                cv2.imshow('last captured 25 frame', frames_queue[2])
            else:
                if len(frames_queue) == 5:
                    cv2.imshow('video playback without 25 frame', frames_queue[2])

        cap.release()
        cv2.destroyAllWindows()
    l2.configure(text='Завершено')
    frames_queue.clear()
    resized_queue.clear()
    frame_time.clear()
    update_img(255 * np.ones(shape=[1, 1, 3], dtype=np.uint8))
    b2.configure(text="НАЧАТЬ")
    if frames_count>0:
        tkinter.messagebox.showinfo('Завершено', 'Найдено ' + str(frames_count) + ' кадров')
    else:
        tkinter.messagebox.showinfo('Завершено', '25 кадр не найден')
    process_state = 0




def resiz(frame):
    x = len(frame[0])
    y = len(frame)
    return cv2.resize(frame, (int(x / (y / 200)), 200))


def update_img(frame):
    global IMG1, IMG2, IMG_N
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(img)
    imgtk = ImageTk.PhotoImage(im)
    if IMG_N == 1:
        IMG2 = imgtk
        l3.configure(image=IMG2)
        IMG_N = 0
    else:
        IMG1 = imgtk
        l3.configure(image=IMG1)
        IMG_N = 1


def show_preview(video_url):
    global src
    src = video_url
    cap = cv2.VideoCapture(src)
    ret, frame = cap.read()
    if ret:
        x = len(frame[0])
        y = len(frame)
        frame = resiz(frame)
        update_img(frame)
        l2.configure(text='')
        cap.release()
    else:
        l2.configure(text="Видео не выбрано")
        update_img(255 * np.ones(shape=[1, 1, 3], dtype=np.uint8))


def choose_file():
    filename = filedialog.askopenfilename(initialdir=os.getcwd(), title="Выбор файла", filetypes=(
        ("Файлы видео", "*.mp4;*.wmv;*.mpg;*.avi;*.m4a;*.wtv;*.flv;*.mkv"), ("Все файлы", "*.*")))
    e1.delete(0, END)
    e1.insert(0, Path(filename))
    e2.delete(0, END)
    e2.insert(0, str(Path(os.path.splitext(Path(filename))[0])))


root = Tk()
root.title("Программа для поиска 25 кадра")


def cb_th(s):
    # Проверка, что это ссылка на youtube
    if re.match('https?://.*youtube.*watch\?v=', s) or re.match('https?://youtu.be/.*', s):
        print('youtube-dl', s)
        show_preview(get_video_url(s))

    # Если начинается на http, то это может быть прямая ссылка на видео
    elif len(s) > 5 and s[:4] == 'http':
        print('url-', s)
        show_preview(s)
    else:
        # Иначе это может быть путь к файлу
        print(s)
        try:
            fp = open(s, 'r')
            if fp:
                fp.close()
                l2.configure(text='')
                show_preview(s)
        except:
            update_img(255 * np.ones(shape=[1, 1, 3], dtype=np.uint8))


def callback(sv):
    s = sv.get()
    svt = threading.Thread(target=cb_th, args=(s,))
    svt.start()


sv = StringVar()
sv.trace("w", lambda name, index, mode, sv=sv: callback(sv))

e1 = Entry(width=60, textvariable=sv)
e2 = Entry(width=60)
e1.insert(0, Path(os.getcwd()))
e2.insert(0, Path(os.getcwd()))

b1 = Button(text="Обзор...", command=choose_file)
l1 = Label(text="Файл или ссылка:")
l2 = Label(text="Видео не выбрано")
l3 = Label()
b2 = Button(text="НАЧАТЬ", command=th_process)
l5 = Label(text="Выходная папка:")

l1.grid(row=0, column=0)
e1.grid(row=0, column=1)
b1.grid(row=0, column=2)
l5.grid(row=1, column=0)
e2.grid(row=1, column=1)
l2.grid(row=2, column=1)
l3.grid(row=3, column=1)
b2.grid(row=3, column=2)
root.mainloop()
