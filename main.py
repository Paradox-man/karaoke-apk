# -*- coding: utf-8 -*-
"""Aplikasi Karaoke (Kivy) - tempel link YouTube, hasilkan musik tanpa vokal."""

import os
import re
import glob
import wave
import threading

import numpy as np
from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

SR = 44100


def pilih_folder(fallback):
    kandidat = []
    if platform == "android":
        try:
            from android.storage import primary_external_storage_path
            kandidat.append(os.path.join(primary_external_storage_path(), "Music", "Karaoke"))
        except Exception:
            pass
    kandidat.append(fallback)
    for d in kandidat:
        try:
            os.makedirs(os.path.join(d, "asli"), exist_ok=True)
            os.makedirs(os.path.join(d, "instrumental"), exist_ok=True)
            uji = os.path.join(d, ".uji")
            with open(uji, "w") as f:
                f.write("ok")
            os.remove(uji)
            return d
        except Exception:
            continue
    return fallback


def bersihkan_link(url):
    url = url.strip()
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", url)
    if m:
        return "https://www.youtube.com/watch?v=" + m.group(1)
    return url


def nama_aman(teks):
    teks = re.sub(r"[^\w\- ]+", "", teks, flags=re.UNICODE).strip()
    return re.sub(r"\s+", "_", teks)[:80] or "lagu"


def unduh(url, folder):
    from yt_dlp import YoutubeDL

    opsi = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": os.path.join(folder, "asli", "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    with YoutubeDL(opsi) as y:
        info = y.extract_info(url, download=True)
        path = y.prepare_filename(info)
    return path, info.get("title", "lagu")


def lowpass(x, n=315):
    x = x.astype(np.float64)
    c = np.concatenate(([0.0], np.cumsum(x)))
    y = (c[n:] - c[:-n]) / n
    kiri = n // 2
    kanan = len(x) - len(y) - kiri
    return np.pad(y, (kiri, kanan), mode="edge")


def baca_stereo(path):
    import av

    wadah = av.open(path)
    aliran = wadah.streams.audio[0]
    rs = av.AudioResampler(format="s16", layout="stereo", rate=SR)
    potongan = []

    def ambil(hasil):
        if hasil is None:
            return
        if not isinstance(hasil, (list, tuple)):
            hasil = [hasil]
        for fr in hasil:
            a = fr.to_ndarray().reshape(-1, 2)
            potongan.append(a.astype(np.float32) / 32768.0)

    for frame in wadah.decode(aliran):
        ambil(rs.resample(frame))
    try:
        ambil(rs.resample(None))
    except Exception:
        pass
    wadah.close()
    if not potongan:
        raise RuntimeError("Audio tidak bisa dibaca")
    return np.concatenate(potongan, axis=0)


def hapus_vokal(src, dst_wav):
    data = baca_stereo(src)
    L, R = data[:, 0], data[:, 1]
    sisi = (L - R) / 2.0
    bass = lowpass((L + R) / 2.0)
    sisi_hp = sisi - lowpass(sisi)
    out = (bass + sisi_hp).astype(np.float32)
    puncak = float(np.max(np.abs(out))) or 1.0
    out = out / puncak * 0.95
    pcm = (np.stack([out, out], axis=1) * 32767).astype(np.int16)
    with wave.open(dst_wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


class KaraokeApp(App):
    title = "Karaoke"

    def build(self):
        self.folder = pilih_folder(self.user_data_dir)
        self.suara = None

        root = BoxLayout(orientation="vertical", padding=10, spacing=8)
        self.input = TextInput(
            hint_text="Tempel link YouTube / YouTube Music",
            multiline=False, size_hint_y=None, height=120,
        )
        self.tombol = Button(text="Buat Karaoke", size_hint_y=None, height=120)
        self.tombol.bind(on_release=self.mulai)
        self.status = Label(
            text="Siap.\nLokasi: " + self.folder, size_hint_y=None, height=200,
            halign="center", valign="middle",
        )
        self.status.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        self.daftar = BoxLayout(orientation="vertical", size_hint_y=None, spacing=6)
        self.daftar.bind(minimum_height=self.daftar.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.daftar)

        root.add_widget(self.input)
        root.add_widget(self.tombol)
        root.add_widget(self.status)
        root.add_widget(sv)
        self.segarkan()
        return root

    def on_start(self):
        if platform == "android":
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                ])
            except Exception:
                pass

    def set_status(self, teks):
        Clock.schedule_once(lambda dt: setattr(self.status, "text", teks))

    def mulai(self, *_):
        url = bersihkan_link(self.input.text)
        if not url:
            self.status.text = "Link masih kosong."
            return
        self.tombol.disabled = True
        threading.Thread(target=self.kerja, args=(url,), daemon=True).start()

    def kerja(self, url):
        try:
            self.set_status("1/2 Mengunduh audio...")
            asli, judul = unduh(url, self.folder)
            self.set_status("2/2 Menghilangkan vokal (tunggu sebentar)...")
            tujuan = os.path.join(self.folder, "instrumental", nama_aman(judul) + "_karaoke.wav")
            hapus_vokal(asli, tujuan)
            self.set_status("Selesai!\n" + tujuan)
            Clock.schedule_once(lambda dt: self.segarkan())
        except Exception as e:
            self.set_status("Gagal: " + str(e)[:300])
        finally:
            Clock.schedule_once(lambda dt: setattr(self.tombol, "disabled", False))

    def segarkan(self):
        self.daftar.clear_widgets()
        file = sorted(glob.glob(os.path.join(self.folder, "instrumental", "*.wav")))
        if not file:
            self.daftar.add_widget(Label(text="Belum ada lagu karaoke.", size_hint_y=None, height=80))
        for f in file:
            b = Button(text=os.path.basename(f), size_hint_y=None, height=110)
            b.bind(on_release=lambda w, p=f: self.putar(p))
            self.daftar.add_widget(b)

    def putar(self, path):
        if self.suara:
            self.suara.stop()
        self.suara = SoundLoader.load(path)
        if self.suara:
            self.suara.play()
            self.status.text = "Memutar: " + os.path.basename(path)
        else:
            self.status.text = "Tidak bisa memutar file ini."


if __name__ == "__main__":
    KaraokeApp().run()
