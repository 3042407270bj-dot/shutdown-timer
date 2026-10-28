# -*- coding: utf-8 -*-
"""定时关机助手 · 现代版

功能：
  · 定点关机 / 倒计时关机，支持关机、重启、休眠三种任务
  · 实时倒计时 + 环形进度动画
  · 关机前 1 分钟弹窗提醒，可取消 / 推迟 10 分钟
  · 一键取消任务；关机与重启由系统计时，关闭程序不影响任务
  · 快捷时间（+1/+2 小时、15/30/60/120 分钟）
  · 深 / 浅主题切换、窗口置顶、自动记住上次设置

仅依赖 Python 标准库，Windows 10/11 双击即可运行。
"""

import base64
import ctypes
import datetime
import json
import math
import os
import subprocess
import time
import winreg
import tkinter as tk
import tkinter.messagebox as messagebox

try:  # PIL 用于抗锯齿渲染（缺省时自动退回 tkinter 矢量绘制）
    from PIL import Image, ImageDraw, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False

try:  # pystray 用于系统托盘（缺省时隐藏托盘相关功能）
    import pystray
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False

# ---------------- 高 DPI 支持 ----------------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

DPI = 96
try:
    DPI = int(ctypes.windll.user32.GetDpiForSystem())
except Exception:
    pass
SC = max(1.0, DPI / 96.0)


def S(v):
    """布局尺寸按屏幕缩放"""
    return int(round(v * SC))


def FS(px):
    """像素字号（负数表示按像素解析，布局稳定）"""
    return -max(9, int(round(px * SC)))


FONT = "Microsoft YaHei UI"
IS_WIN = os.name == "nt"

THEMES = {
    "dark": dict(
        bg="#0e1320", card="#161d2f", card2="#1d2640", stroke="#273252",
        text="#eaeefb", sub="#8a93b2", faint="#5b6484",
        accent="#5b8cff", accent_hi="#7aa5ff", accent_lo="#3f6fe8",
        ok="#3ddc97", warn="#ffb454", danger="#ff6b6b",
        entry="#111830",
    ),
    "light": dict(
        bg="#f3f5fa", card="#ffffff", card2="#eaeef7", stroke="#dfe5f2",
        text="#1c2333", sub="#6b7490", faint="#a8afc6",
        accent="#4d7cff", accent_hi="#6d94ff", accent_lo="#3a63d6",
        ok="#18b566", warn="#e8930c", danger="#e5484d",
        entry="#f6f8fd",
    ),
}

FLAG = {"shutdown": "/s", "restart": "/r"}

# ---------------- 多语言 ----------------
LANGS = ["zh", "en", "fr", "ru", "es", "ar", "zh-TW", "la"]
LANG_NAME = {"zh": "简体中文", "en": "English", "fr": "Français", "ru": "Русский",
             "es": "Español", "ar": "العربية", "zh-TW": "繁體中文", "la": "Latina"}

I18N = {
"zh": dict(
    title="定时关机助手", date_fmt="%m月%d日", wd=("周一", "周二", "周三", "周四", "周五", "周六", "周日"),
    idle_sub="当前时间 · 暂无任务", executing="执行中",
    mode_cd="倒计时", mode_at="定点", unit_min_after=" 分钟后", unit_h=" 时  ", unit_m=" 分",
    plus1h="+1小时", plus2h="+2小时", task_lbl="任务",
    act_shutdown="关机", act_restart="重启", act_sleep="休眠",
    remind_lbl="关机前 1 分钟弹窗提醒我", btn_start="开始任务", btn_cancel="取消任务",
    hint="关机与重启由系统计时，关闭本程序任务依然有效",
    err_time_invalid="请输入有效的小时和分钟", err_time_range="时间范围：时 0-23，分 0-59",
    err_time_past="定点时间需晚于当前时间", err_minutes_invalid="请输入有效的分钟数",
    err_minutes_positive="分钟数需大于 0", err_admin="设置失败：请尝试以管理员身份运行",
    err_no_task="当前没有进行中的任务", err_cancel_fail="取消失败：任务可能已被取消",
    err_postpone_fail="推迟失败，请手动重新设置", err_sleep_fail="休眠失败：系统可能未启用休眠功能",
    ok_set="已设定 {t} {w}", sleep_tip="（休眠由本程序计时，请保持程序运行）",
    ok_cancel="已取消定时任务", ok_cancel_sleep="已取消休眠任务",
    ok_postpone="任务已推迟 10 分钟", ok_slept="已执行休眠",
    quick_filled="已填入 {v}，点击「开始任务」生效",
    warn_soon="即将{w}", warn_body="{w}任务将于 {t} 执行，请保存好工作内容",
    btn_wcancel="取消任务", btn_postpone="推迟10分钟", btn_ignore="忽略",
    close_title="退出确认", close_body="有一个休眠任务正在进行中，\n退出后该任务将被取消。确定退出吗？",
    lang_set="语言已切换：{n}",
    repeat_lbl="每天重复执行", auto_lbl="跟随系统主题",
    tray_lbl="关闭时最小化到托盘", tray_show="显示主窗口", tray_exit="退出",
    repeat_ok="已自动安排明天 {t} {w}", tray_tip="已最小化到托盘，双击图标恢复",
),
"en": dict(
    title="Shutdown Timer", date_fmt="%b %d", wd=("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    idle_sub="Current time · No task", executing="Running…",
    mode_cd="Countdown", mode_at="Scheduled", unit_min_after=" min", unit_h=" h  ", unit_m=" min",
    plus1h="+1 hour", plus2h="+2 hours", task_lbl="Action",
    act_shutdown="Shut down", act_restart="Restart", act_sleep="Sleep",
    remind_lbl="Remind me 1 minute before", btn_start="Start", btn_cancel="Cancel task",
    hint="Shutdown & restart are timed by the system — tasks survive closing this app",
    err_time_invalid="Enter a valid hour and minute", err_time_range="Hour 0–23, minute 0–59",
    err_time_past="Scheduled time must be in the future", err_minutes_invalid="Enter a valid number of minutes",
    err_minutes_positive="Minutes must be greater than 0", err_admin="Failed — try running as administrator",
    err_no_task="No running task", err_cancel_fail="Cancel failed — the task may already be gone",
    err_postpone_fail="Postpone failed — please set it again", err_sleep_fail="Sleep failed — hibernation may be disabled",
    ok_set="Task set: {w} at {t}", sleep_tip=" (sleep is timed by this app — keep it running)",
    ok_cancel="Task cancelled", ok_cancel_sleep="Sleep task cancelled",
    ok_postpone="Postponed by 10 minutes", ok_slept="Sleep started",
    quick_filled="{v} filled — press Start to apply",
    warn_soon="{w} starting soon", warn_body="{w} will run at {t}. Save your work!",
    btn_wcancel="Cancel", btn_postpone="+10 min", btn_ignore="Dismiss",
    close_title="Confirm exit", close_body="A sleep task is running.\nIt will be lost if you exit. Quit anyway?",
    lang_set="Language: {n}",
    repeat_lbl="Repeat daily", auto_lbl="Follow system theme",
    tray_lbl="Minimize to tray on close", tray_show="Show window", tray_exit="Exit",
    repeat_ok="Tomorrow {w} at {t} scheduled", tray_tip="Minimized to tray — double-click icon to restore",
),
"fr": dict(
    title="Minuterie d'extinction", date_fmt="%d/%m", wd=("Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"),
    idle_sub="Heure actuelle · Aucune tâche", executing="En cours…",
    mode_cd="Minuterie", mode_at="Programmé", unit_min_after=" min", unit_h=" h  ", unit_m=" min",
    plus1h="+1 heure", plus2h="+2 heures", task_lbl="Action",
    act_shutdown="Éteindre", act_restart="Redémarrer", act_sleep="Veille",
    remind_lbl="Me rappeler 1 minute avant", btn_start="Démarrer", btn_cancel="Annuler la tâche",
    hint="Extinction et redémarrage programmés par le système — la tâche persiste après fermeture",
    err_time_invalid="Saisissez heure et minute valides", err_time_range="Heure 0–23, minute 0–59",
    err_time_past="L'heure doit être dans le futur", err_minutes_invalid="Saisissez un nombre de minutes valide",
    err_minutes_positive="Les minutes doivent être supérieures à 0", err_admin="Échec — essayez en administrateur",
    err_no_task="Aucune tâche en cours", err_cancel_fail="Annulation impossible — la tâche a peut-être disparu",
    err_postpone_fail="Report impossible — recommencez", err_sleep_fail="Échec de la veille — hibernation peut-être désactivée",
    ok_set="Tâche définie : {w} à {t}", sleep_tip=" (veille minutée par l'application — laissez-la ouverte)",
    ok_cancel="Tâche annulée", ok_cancel_sleep="Tâche de veille annulée",
    ok_postpone="Reportée de 10 minutes", ok_slept="Veille lancée",
    quick_filled="{v} rempli — cliquez sur Démarrer",
    warn_soon="{w} imminente", warn_body="{w} à {t}. Sauvegardez votre travail !",
    btn_wcancel="Annuler", btn_postpone="+10 min", btn_ignore="Ignorer",
    close_title="Confirmer la fermeture", close_body="Une tâche de veille est en cours.\nElle sera perdue si vous quittez. Fermer quand même ?",
    lang_set="Langue : {n}",
    repeat_lbl="Répéter chaque jour", auto_lbl="Suivre le thème du système",
    tray_lbl="Réduire dans la zone de notification", tray_show="Afficher la fenêtre", tray_exit="Quitter",
    repeat_ok="Demain : {w} à {t} programmé", tray_tip="Réduit dans la zone de notification",
),
"ru": dict(
    title="Таймер выключения", date_fmt="%d.%m", wd=("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
    idle_sub="Текущее время · Нет задач", executing="Выполняется…",
    mode_cd="Отсчёт", mode_at="По времени", unit_min_after=" мин", unit_h=" ч  ", unit_m=" мин",
    plus1h="+1 час", plus2h="+2 часа", task_lbl="Действие",
    act_shutdown="Выключение", act_restart="Перезагрузка", act_sleep="Спящий режим",
    remind_lbl="Напомнить за 1 минуту", btn_start="Запустить", btn_cancel="Отменить задачу",
    hint="Выключение и перезагрузка выполняются системой — задача сохранится после закрытия",
    err_time_invalid="Введите корректные час и минуту", err_time_range="Час 0–23, минута 0–59",
    err_time_past="Время должно быть в будущем", err_minutes_invalid="Введите корректное число минут",
    err_minutes_positive="Минуты должны быть больше 0", err_admin="Не удалось — запустите от имени администратора",
    err_no_task="Нет активных задач", err_cancel_fail="Не удалось отменить — задача уже исчезла",
    err_postpone_fail="Не удалось отложить — настройте заново", err_sleep_fail="Не удалось — возможно, спящий режим отключён",
    ok_set="Задача: {w} в {t}", sleep_tip=" (отсчёт ведёт программа — не закрывайте её)",
    ok_cancel="Задача отменена", ok_cancel_sleep="Задача сна отменена",
    ok_postpone="Отложено на 10 минут", ok_slept="Сон запущен",
    quick_filled="{v} — нажмите «Запустить»",
    warn_soon="Скоро: {w}", warn_body="{w} в {t}. Сохраните работу!",
    btn_wcancel="Отменить", btn_postpone="+10 мин", btn_ignore="Скрыть",
    close_title="Подтвердите выход", close_body="Выполняется задача сна.\nОна будет отменена при выходе. Выйти?",
    lang_set="Язык: {n}",
    repeat_lbl="Повторять ежедневно", auto_lbl="Системная тема",
    tray_lbl="Свернуть в трей", tray_show="Показать окно", tray_exit="Выход",
    repeat_ok="На завтра: {w} в {t}", tray_tip="Свернуто в трей — дважды щелкните значок",
),
"es": dict(
    title="Apagado programado", date_fmt="%d/%m", wd=("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"),
    idle_sub="Hora actual · Sin tareas", executing="Ejecutando…",
    mode_cd="Cuenta atrás", mode_at="Hora fija", unit_min_after=" min", unit_h=" h  ", unit_m=" min",
    plus1h="+1 hora", plus2h="+2 horas", task_lbl="Acción",
    act_shutdown="Apagar", act_restart="Reiniciar", act_sleep="Suspender",
    remind_lbl="Avisarme 1 minuto antes", btn_start="Iniciar", btn_cancel="Cancelar tarea",
    hint="Apagado y reinicio los programa el sistema — la tarea vive aunque cierres la app",
    err_time_invalid="Introduce hora y minuto válidos", err_time_range="Hora 0–23, minuto 0–59",
    err_time_past="La hora debe ser futura", err_minutes_invalid="Introduce minutos válidos",
    err_minutes_positive="Los minutos deben ser mayores que 0", err_admin="Error — prueba como administrador",
    err_no_task="No hay tareas activas", err_cancel_fail="No se pudo cancelar — quizá ya desapareció",
    err_postpone_fail="No se pudo posponer — configúralo de nuevo", err_sleep_fail="Error al suspender — quizá la hibernación está desactivada",
    ok_set="Tarea: {w} a las {t}", sleep_tip=" (esta app cuenta el tiempo — mantenla abierta)",
    ok_cancel="Tarea cancelada", ok_cancel_sleep="Tarea de suspensión cancelada",
    ok_postpone="Pospuesta 10 minutos", ok_slept="Suspensión iniciada",
    quick_filled="{v} — pulsa Iniciar",
    warn_soon="{w} inminente", warn_body="{w} a las {t}. ¡Guarda tu trabajo!",
    btn_wcancel="Cancelar", btn_postpone="+10 min", btn_ignore="Ignorar",
    close_title="Confirmar salida", close_body="Hay una tarea de suspensión activa.\nSe perderá al salir. ¿Salir igualmente?",
    lang_set="Idioma: {n}",
    repeat_lbl="Repetir a diario", auto_lbl="Tema del sistema",
    tray_lbl="Minimizar a la bandeja", tray_show="Mostrar ventana", tray_exit="Salir",
    repeat_ok="Mañana: {w} a las {t}", tray_tip="Minimizado a la bandeja",
),
"ar": dict(
    title="مؤقت إيقاف التشغيل", date_fmt="%d/%m", wd=("الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"),
    idle_sub="الوقت الحالي · لا مهام", executing="جارٍ التنفيذ…",
    mode_cd="عد تنازلي", mode_at="وقت محدد", unit_min_after=" دقيقة", unit_h=" س  ", unit_m=" د",
    plus1h="+1 ساعة", plus2h="+2 ساعة", task_lbl="الإجراء",
    act_shutdown="إيقاف", act_restart="إعادة تشغيل", act_sleep="سكون",
    remind_lbl="ذكّرني قبل دقيقة", btn_start="بدء المهمة", btn_cancel="إلغاء المهمة",
    hint="يُدير النظام توقيت الإيقاف وإعادة التشغيل — تبقى المهمة بعد إغلاق التطبيق",
    err_time_invalid="أدخل ساعة ودقيقة صحيحتين", err_time_range="الساعة 0-23 والدقيقة 0-59",
    err_time_past="يجب أن يكون الوقت في المستقبل", err_minutes_invalid="أدخل عدد دقائق صحيحًا",
    err_minutes_positive="يجب أن تكون الدقائق أكبر من 0", err_admin="فشل — جرّب التشغيل كمسؤول",
    err_no_task="لا توجد مهام جارية", err_cancel_fail="تعذّر الإلغاء — ربما أُلغيت المهمة بالفعل",
    err_postpone_fail="تعذّر التأجيل — أعد الإعداد", err_sleep_fail="فشل السكون — ربما يكون الإسبات معطلًا",
    ok_set="تم التعيين: {w} الساعة {t}", sleep_tip=" (يحسب التطبيق الوقت — أبقه مفتوحًا)",
    ok_cancel="أُلغيت المهمة", ok_cancel_sleep="أُلغيت مهمة السكون",
    ok_postpone="أُجّلت 10 دقائق", ok_slept="بدأ السكون",
    quick_filled="{v} — اضغط «بدء المهمة»",
    warn_soon="{w} قريبًا", warn_body="{w} الساعة {t}. احفظ عملك!",
    btn_wcancel="إلغاء", btn_postpone="+10 د", btn_ignore="تجاهل",
    close_title="تأكيد الخروج", close_body="توجد مهمة سكون جارية.\nستُفقد عند الخروج. الخروج على أي حال؟",
    lang_set="اللغة: {n}",
    repeat_lbl="تكرار يومي", auto_lbl="مظهر النظام",
    tray_lbl="التصغير إلى علبة النظام", tray_show="إظهار النافذة", tray_exit="خروج",
    repeat_ok="الغد: {w} الساعة {t}", tray_tip="تم التصغير إلى العلبة",
),
"zh-TW": dict(
    title="定時關機助手", date_fmt="%m月%d日", wd=("週一", "週二", "週三", "週四", "週五", "週六", "週日"),
    idle_sub="現在時間 · 無任務", executing="執行中",
    mode_cd="倒數", mode_at="定時", unit_min_after=" 分鐘後", unit_h=" 時  ", unit_m=" 分",
    plus1h="+1小時", plus2h="+2小時", task_lbl="任務",
    act_shutdown="關機", act_restart="重新啟動", act_sleep="睡眠",
    remind_lbl="關機前 1 分鐘彈窗提醒我", btn_start="開始任務", btn_cancel="取消任務",
    hint="關機與重新啟動由系統計時，關閉本程式任務依然有效",
    err_time_invalid="請輸入有效的小時和分鐘", err_time_range="時間範圍：時 0-23，分 0-59",
    err_time_past="定時時間需晚於目前時間", err_minutes_invalid="請輸入有效的分鐘數",
    err_minutes_positive="分鐘數需大於 0", err_admin="設定失敗：請以系統管理員身分執行",
    err_no_task="目前沒有進行中的任務", err_cancel_fail="取消失敗：任務可能已被取消",
    err_postpone_fail="延後失敗，請重新設定", err_sleep_fail="睡眠失敗：系統可能未啟用休眠功能",
    ok_set="已設定 {t} {w}", sleep_tip="（睡眠由本程式計時，請保持程式執行）",
    ok_cancel="已取消定時任務", ok_cancel_sleep="已取消睡眠任務",
    ok_postpone="任務已延後 10 分鐘", ok_slept="已進入睡眠",
    quick_filled="已填入 {v}，點擊「開始任務」生效",
    warn_soon="即將{w}", warn_body="{w}任務將於 {t} 執行，請保存好工作內容",
    btn_wcancel="取消任務", btn_postpone="延後10分鐘", btn_ignore="忽略",
    close_title="結束確認", close_body="有睡眠任務進行中，\n結束後任務將被取消。確定離開嗎？",
    lang_set="語言已切換：{n}",
    repeat_lbl="每天重複執行", auto_lbl="跟隨系統主題",
    tray_lbl="關閉時最小化到通知區", tray_show="顯示主視窗", tray_exit="結束",
    repeat_ok="已自動安排明天 {t} {w}", tray_tip="已最小化到通知區，雙擊圖示恢復",
),
"la": dict(
    title="Tempus Exstinctionis", date_fmt="%d.%m", wd=("Lun", "Mar", "Mer", "Iov", "Ven", "Sab", "Sol"),
    idle_sub="Hora nunc · Nulla officia", executing="Agitur…",
    mode_cd="Numerus", mode_at="Hora statuta", unit_min_after=" minuta", unit_h=" h  ", unit_m=" min",
    plus1h="+1 hora", plus2h="+2 horae", task_lbl="Officium",
    act_shutdown="Exstinctio", act_restart="Reinitium", act_sleep="Somnus",
    remind_lbl="Mone me 1 minuta ante", btn_start="Incipere", btn_cancel="Officium tollere",
    hint="Exstinctio et reinitium a systemate numerantur — officium manet etiam si app claudatur",
    err_time_invalid="Horam minutamque validam scribe", err_time_range="Hora 0–23, minuta 0–59",
    err_time_past="Hora futura esse debet", err_minutes_invalid="Numerum minutorum validum scribe",
    err_minutes_positive="Minuta maior quam 0 esse debent", err_admin="Defecit — scribe ut administrator",
    err_no_task="Nullum officium agitur", err_cancel_fail="Tollere non potui — fortasse officium iam abiit",
    err_postpone_fail="Differre non potui — iterum conare", err_sleep_fail="Somnus defecit — fortasse somnus hiemalis vetitus est",
    ok_set="Officium: {w} hora {t}", sleep_tip=" (app numerat — eam apud te serva)",
    ok_cancel="Officium abolitum est", ok_cancel_sleep="Officium somni abolitum est",
    ok_postpone="10 minutis diffusum", ok_slept="Somnus incepit",
    quick_filled="{v} — Incipere preme",
    warn_soon="{w} mox", warn_body="{w} hora {t}. Serva opus tuum!",
    btn_wcancel="Tolle", btn_postpone="+10 min", btn_ignore="Dissolve",
    close_title="Confirmare exitum", close_body="Officium somni agitur.\nPeribit si exieris. Exire tamen?",
    lang_set="Lingua: {n}",
    repeat_lbl="Repetire cotidie", auto_lbl="Theme systematis sequi",
    tray_lbl="Minimizare in area notific", tray_show="Monstrare fenestram", tray_exit="Exire",
    repeat_ok="Cras: {w} hora {t}", tray_tip="In area notificationis minimizatum",
)}

CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ShutdownTimer")
CFG_FILE = os.path.join(CFG_DIR, "config.json")

# 应用图标（内嵌 base64，首次运行时写出到 %APPDATA%，单文件分发也能显示图标）
ICON_B64 = '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'


def ensure_app_icon():
    """写出内嵌图标并返回路径；失败返回 None，不影响程序运行"""
    try:
        path = os.path.join(CFG_DIR, "icon.ico")
        if not os.path.exists(path):
            os.makedirs(CFG_DIR, exist_ok=True)
            with open(path, "wb") as f:
                f.write(base64.b64decode(ICON_B64))
        return path
    except Exception:
        return None


# ---------------- 基础工具 ----------------
def mix(c1, c2, t):
    """两个 #rrggbb 颜色插值"""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _rgba(hx):
    hx = hx.lstrip("#")
    return (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16), 255)


def round_rect(cv, x1, y1, x2, y2, r, fill=None, outline=None, width=1, ss=6):
    """圆角矩形：PIL 超采样抗锯齿渲染；无 PIL 时退回平滑多边形
    ss=6 为静态高清；动画中间帧传 ss=2 降低渲染成本"""
    if HAS_PIL and fill is not None:
        w, h = int(round(x2 - x1)), int(round(y2 - y1))
        img = Image.new("RGBA", (max(1, w * ss), max(1, h * ss)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        o = width if outline else 0
        d.rounded_rectangle([o, o, w * ss - o - 1, h * ss - o - 1],
                            radius=max(1, int(r * ss)), fill=_rgba(fill),
                            outline=_rgba(outline) if outline else None,
                            width=max(1, int(o * ss)) if o else 0)
        ph = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
        store = getattr(cv, "_pil_refs", None)
        if store is None:
            store = cv._pil_refs = []
        store.append(ph)
        if len(store) > 60:
            del store[:30]
        return cv.create_image(x1, y1, image=ph, anchor="nw")
    r = max(1, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, fill=fill,
                             outline=outline, width=width if outline else 0)


def render_ring_photo(size, thick, frac, track, accent, end_col, danger_col, danger):
    """整环一次抗锯齿渲染：轨道 + 渐变进度弧（12 点起、逆时针推进）+ 端点圆头"""
    ss = 4
    img = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = thick // 2 + 2
    bbox = [pad * ss, pad * ss, (size - pad) * ss, (size - pad) * ss]
    lw = max(1, thick * ss)
    d.arc(bbox, start=0, end=360, fill=_rgba(track), width=lw)
    if frac > 0.003:
        total = 359.9 * frac
        col = danger_col if danger else end_col
        if danger:
            d.arc(bbox, start=270 - total, end=270, fill=_rgba(col), width=lw)
        else:
            segs = max(2, int(48 * frac))
            for i in range(segs):
                a0 = 270 - total + total * i / segs
                a1 = 270 - total + total * (i + 1) / segs
                d.arc(bbox, start=a0, end=a1 + 0.4,
                      fill=_rgba(mix(end_col, accent, i / segs)), width=lw)
        ang = math.radians(270 - total)
        c = size / 2 * ss
        R = (size / 2 - pad) * ss
        ex, ey = c + R * math.cos(ang), c + R * math.sin(ang)
        rr = S(7) * ss
        d.ellipse([ex - rr, ey - rr, ex + rr, ey + rr], fill=_rgba(col))
    return ImageTk.PhotoImage(img.resize((size, size), Image.LANCZOS))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def fmt_sec(s):
    s = max(0, int(s))
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def run_cmd(args):
    """静默执行命令，返回是否成功"""
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run(args, capture_output=True, creationflags=flags).returncode == 0
    except Exception:
        return False


def load_cfg():
    try:
        with open(CFG_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def system_dark():
    """读取 Windows 深色模式设置（读不到时默认深色）"""
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        v, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
        return v == 0
    except OSError:
        return True


def tray_logo_image():
    """生成托盘用的 128px 应用图标"""
    s = 128
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    grad = Image.new("RGBA", (s, s))
    gp = grad.load()
    for yy in range(s):
        for xx in range(s):
            t = (xx + yy) / (2 * (s - 1))
            gp[xx, yy] = tuple(int(BLUE_P[i] + (PURPLE_P[i] - BLUE_P[i]) * t) for i in range(3)) + (255,)
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.24), fill=255)
    im.paste(grad, (0, 0), m)
    od = ImageDraw.Draw(im)
    cx = cy = s / 2
    R = s * 0.30
    lw = int(s * 0.075)
    od.arc([cx - R, cy - R, cx + R, cy + R], start=-68, end=248, fill=(255, 255, 255, 255), width=lw)
    od.line([(cx, cy), (cx, cy - R + s * 0.01)], fill=(255, 255, 255, 255), width=lw)
    L = R * 0.68; a = math.radians(46)
    od.line([(cx, cy), (cx + L * math.cos(a), cy + L * math.sin(a))], fill=(255, 255, 255, 255), width=lw)
    rr = lw / 2
    od.ellipse([cx + L * math.cos(a) - rr, cy + L * math.sin(a) - rr,
                cx + L * math.cos(a) + rr, cy + L * math.sin(a) + rr], fill=(255, 255, 255, 255))
    od.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(255, 255, 255, 255))
    return im


BLUE_P, PURPLE_P = (91, 140, 255), (139, 92, 246)


# ---------------- 自绘组件 ----------------
class Card(tk.Canvas):
    """圆角卡片，inner 为内容容器"""

    def __init__(self, parent, app, w, h, r=None):
        super().__init__(parent, width=w, height=h, bg=parent["bg"], highlightthickness=0)
        self.inner = tk.Frame(self, bg=app.T["card"])
        round_rect(self, S(1), S(1), w - S(1), h - S(1), r or S(18),
                   fill=app.T["card"], outline=app.T["stroke"], width=S(1))
        self.create_window((S(12), S(12)), window=self.inner, anchor="nw",
                           width=w - S(24), height=h - S(24))


class Btn(tk.Canvas):
    """圆角按钮（solid / danger / soft / ghost 四种风格，带悬停与按压反馈）"""

    def __init__(self, parent, app, text, command, w, h=S(44), style="solid", font_size=13):
        super().__init__(parent, width=w, height=h, bg=parent["bg"],
                         highlightthickness=0, cursor="hand2")
        self.app, self.text, self.command = app, text, command
        self.W, self.H, self.style, self.fs = w, h, style, font_size
        self._down = False
        self.bind("<Enter>", lambda e: self._paint(False, False))
        self.bind("<Leave>", lambda e: self._paint(False, False))
        self.bind("<ButtonPress-1>", lambda e: self._paint(True, True))
        self.bind("<ButtonRelease-1>", self._release)
        self._paint(False, False)

    def _colors(self, hover):
        T = self.app.T
        if self.style == "solid":
            return mix(T["accent"], "#ffffff", 0.14) if hover else T["accent"], None, "#ffffff"
        if self.style == "danger":
            return mix(T["danger"], "#ffffff", 0.12) if hover else T["danger"], None, "#ffffff"
        if self.style == "ghost":
            if hover:
                return T["card2"], T["danger"], T["danger"]
            return T["card"], T["stroke"], T["sub"]
        return mix(T["card2"], T["text"], 0.08) if hover else T["card2"], T["stroke"], T["text"]

    def _paint(self, hover, pressed):
        fill, outline, fg = self._colors(hover)
        T = self.app.T
        if pressed:
            fill = T["accent_lo"] if self.style == "solid" else mix(T["danger"], "#000000", 0.25)
        self._tween(fill, outline, fg)

    def _tween(self, fill, outline, fg, n=4):
        """颜色平滑过渡：中间帧低倍率渲染，最终帧 6x 高清（连续触发以最新目标为准）"""
        target = (fill, outline, fg)
        if getattr(self, "_cur", None) == target:
            return
        self._anim = getattr(self, "_anim", 0) + 1
        my = self._anim
        start = getattr(self, "_cur", None) or target

        def step(i):
            if my != self._anim:
                return
            f = mix(start[0], fill, i / n)
            o = mix(start[1], outline, i / n) if (outline and start[1]) else outline
            self._cur = (f, o, fg)
            self._redraw(f, o, fg, ss=(6 if i == n else 2))
            if i < n:
                self.after(16, step, i + 1)

        step(0)

    def _redraw(self, fill, outline, fg, ss=6):
        self.delete("all")
        round_rect(self, S(1), S(1), self.W - S(1), self.H - S(1), S(12),
                   fill=fill, outline=outline, width=S(1), ss=ss)
        self.create_text(self.W / 2, self.H / 2, text=self.text, fill=fg,
                         font=(FONT, FS(self.fs), "bold"))

    def _release(self, e):
        inside = 0 <= e.x <= self.W and 0 <= e.y <= self.H
        self._paint(inside, False)
        if inside and self.command:
            self.command()


class Chip(tk.Canvas):
    """可选中标签（单选场景用，带悬停过渡）"""

    def __init__(self, parent, app, text, command, w=S(86), h=S(36)):
        super().__init__(parent, width=w, height=h, bg=parent["bg"],
                         highlightthickness=0, cursor="hand2")
        self.app, self.text, self.command = app, text, command
        self.W, self.H = w, h
        self.selected = False
        self._hover = False
        self._anim = 0
        self._cur = None
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self._hover_(True))
        self.bind("<Leave>", lambda e: self._hover_(False))
        self._render()

    def _hover_(self, v):
        self._hover = v
        self._render()

    def set_selected(self, v):
        self.selected = v
        self._render()

    def _target(self):
        T = self.app.T
        if self.selected:
            return T["accent"], "#ffffff", None
        base = mix(T["card2"], T["text"], 0.07) if self._hover else T["card2"]
        return base, T["sub"], T["stroke"]

    def _render(self):
        bg, fg, outline = self._target()
        if self._cur == (bg, fg, outline):
            return
        self._anim += 1
        my = self._anim
        start = self._cur or (bg, fg, outline)

        def step(i, n=8):
            if my != self._anim:
                return
            t = i / n
            cb = mix(start[0], bg, t)
            cf = mix(start[1], fg, t)
            co = mix(start[2], outline, t) if (outline and start[2]) else outline
            self._cur = (cb, cf, co)
            self.delete("all")
            round_rect(self, S(1), S(1), self.W - S(1), self.H - S(1), S(12),
                       fill=cb, outline=co, width=S(1), ss=(6 if i == n else 2))
            self.create_text(self.W / 2, self.H / 2, text=self.text, fill=cf,
                             font=(FONT, FS(11), "bold"))
            if i < n:
                self.after(16, step, i + 1)

        step(0)


# ---- 顶栏自绘单色图标（避免彩色 emoji 破坏整体风格） ----
def icon_sun(cv, color, bg):
    cx, cy = cv.W / 2, cv.H / 2
    r = S(5)
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")
    for k in range(8):
        a = math.pi / 4 * k
        cv.create_line(cx + (r + S(3)) * math.cos(a), cy + (r + S(3)) * math.sin(a),
                       cx + (r + S(7)) * math.cos(a), cy + (r + S(7)) * math.sin(a),
                       fill=color, width=S(2), capstyle="round")


def icon_moon(cv, color, bg):
    cx, cy = cv.W / 2, cv.H / 2
    r = S(8)
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")
    cv.create_oval(cx - r + S(7), cy - r - S(4), cx + r + S(7), cy + r - S(4),
                   fill=bg, outline="")


def icon_pin(cv, color, bg):
    cx, cy = cv.W / 2, cv.H / 2
    top = cy - S(9)
    cv.create_line(cx - S(8), top, cx + S(8), top, fill=color, width=S(2), capstyle="round")
    cv.create_line(cx, top, cx - S(5), top + S(5), fill=color, width=S(2),
                   capstyle="round", joinstyle="round")
    cv.create_line(cx, top, cx + S(5), top + S(5), fill=color, width=S(2),
                   capstyle="round", joinstyle="round")
    cv.create_line(cx, top + S(5), cx, cy + S(8), fill=color, width=S(2), capstyle="round")


def icon_globe(cv, color, bg):
    cx, cy = cv.W / 2, cv.H / 2
    r = S(9)
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=S(2))
    cv.create_line(cx - r, cy, cx + r, cy, fill=color, width=S(2))
    cv.create_oval(cx - r * 0.42, cy - r, cx + r * 0.42, cy + r, outline=color, width=S(2))


class IconBtn(tk.Canvas):
    """小图标按钮：draw_fn(cv, color, bg) 自绘单色图标，带悬停颜色过渡"""

    def __init__(self, parent, app, draw_fn, command, w=S(34), h=S(32)):
        super().__init__(parent, width=w, height=h, bg=parent["bg"],
                         highlightthickness=0, cursor="hand2")
        self.app, self.draw_fn, self.command = app, draw_fn, command
        self.W, self.H = w, h
        self.sel = False
        self._hover = False
        self._anim = 0
        self._cur = None
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self._hover_(True))
        self.bind("<Leave>", lambda e: self._hover_(False))
        self._render()

    def _hover_(self, v):
        self._hover = v
        self._render()

    def set_selected(self, v):
        self.sel = v
        self._render()

    def _target(self):
        T = self.app.T
        if self.sel:
            return T["accent"], "#ffffff"
        if self._hover:
            return mix(T["card2"], T["text"], 0.07), T["text"]
        return T["card2"], T["sub"]

    def _render(self):
        bg, fg = self._target()
        if self._cur == (bg, fg):
            return
        self._anim += 1
        my = self._anim
        start = self._cur or (bg, fg)

        def step(i, n=8):
            if my != self._anim:
                return
            t = i / n
            cb = mix(start[0], bg, t)
            cf = mix(start[1], fg, t)
            self._cur = (cb, cf)
            self.delete("all")
            round_rect(self, S(1), S(1), self.W - S(1), self.H - S(1), S(10),
                       fill=cb, outline=self.app.T["stroke"], width=S(1),
                       ss=(6 if i == n else 2))
            self.draw_fn(self, cf, cb)
            if i < n:
                self.after(16, step, i + 1)

        step(0)


class Segmented(tk.Canvas):
    """分段选择器，滑块带位移动画"""

    def __init__(self, parent, app, opts, command, w, h=S(44)):
        super().__init__(parent, width=w, height=h, bg=parent["bg"],
                         highlightthickness=0, cursor="hand2")
        self.app, self.opts, self.command = app, opts, command
        self.W, self.H = w, h
        self.pad = S(6)
        self.seg_w = (w - self.pad * (len(opts) + 1)) / len(opts)
        self.knob = None
        self.value = opts[0][0]
        self._anim = 0
        self.txt = {}
        self._bg = round_rect(self, S(1), S(1), w - S(1), h - S(1), S(14),
                              fill=app.T["card2"], outline=app.T["stroke"], width=S(1))
        for i, (k, label) in enumerate(opts):
            x = self.pad + i * self.seg_w + self.seg_w / 2
            self.txt[k] = self.create_text(x, h / 2, text=label,
                                           font=(FONT, FS(12), "bold"), fill=app.T["sub"])
        # 整个控件区域都可点击，按横坐标换算分段（而非仅文字可点）
        self.bind("<Button-1>", self._on_click)

    def _on_click(self, e):
        idx = int((e.x - self.pad) // self.seg_w)
        idx = max(0, min(len(self.opts) - 1, idx))
        self.select(self.opts[idx][0])

    def select(self, key, fire=True):
        if key == self.value and self.knob is not None:
            return
        self.value = key
        idx = [k for k, _ in self.opts].index(key)
        x0 = self.pad + idx * self.seg_w
        T = self.app.T
        start_x = getattr(self, "_knob_x", x0)
        self._anim += 1
        my = self._anim

        def step(i, n=8):
            if my != self._anim:
                return
            xx = start_x + (x0 - start_x) * (i / n)
            if self.knob is not None:
                self.delete(self.knob)
            self.knob = round_rect(self, xx, self.pad + S(2), xx + self.seg_w,
                                   self.H - self.pad - S(2), S(10), fill=T["accent"],
                                   ss=(6 if i == n else 2))
            self.tag_raise(self.knob)
            for item in self.txt.values():
                self.tag_raise(item)
            if i < n:
                self.after(18, step, i + 1)
            else:
                self._knob_x = x0

        step(0)
        for k, item in self.txt.items():
            self.itemconfig(item, fill="#ffffff" if k == key else T["sub"])
        if fire and self.command:
            self.command(key)


class Switch(tk.Canvas):
    """开关，圆点带滑动动画"""

    def __init__(self, parent, app, init=False, command=None):
        self.W, self.H = S(46), S(26)
        super().__init__(parent, width=self.W, height=self.H, bg=parent["bg"],
                         highlightthickness=0, cursor="hand2")
        self.app, self.command = app, command
        self.value = bool(init)
        self._anim = 0
        self.bind("<Button-1>", self._click)
        self._draw(self.value, None)

    def _knx(self, v):
        return self.W - self.H / 2 if v else self.H / 2

    def _click(self, e):
        self.set(not self.value)
        if self.command:
            self.command(self.value)

    def set(self, v, animate=True):
        if v == self.value:
            return
        start = self._knx(self.value)
        self.value = v
        target = self._knx(v)
        self._anim += 1
        my = self._anim

        def step(i, n=8):
            if my != self._anim:
                return
            if animate:
                kx = start + (target - start) * (i / n)
            else:
                kx = target
            self._draw(v, kx, ss=(6 if i == n else 2))
            if i < n:
                self.after(16, step, i + 1)

        step(0)

    def _draw(self, v, kx, ss=6):
        T = self.app.T
        self.delete("all")
        round_rect(self, S(1), S(1), self.W - S(1), self.H - S(1), (self.H - S(2)) / 2,
                   fill=T["accent"] if v else T["card2"],
                   outline=T["accent"] if v else T["stroke"], width=S(1), ss=ss)
        kx = self._knx(v) if kx is None else kx
        r = self.H / 2 - S(4)
        self.create_oval(kx - r, self.H / 2 - r, kx + r, self.H / 2 + r,
                         fill="#ffffff", outline="")


# ---------------- 提醒弹窗 ----------------
class WarnWindow:
    """关机前提醒：右下角滑入，可拖动，支持取消 / 推迟 / 忽略"""

    def __init__(self, app, remain):
        self.app = app
        self.word = app.t("act_" + app.task["type"])
        self.remain = remain
        T = app.T
        w, h = S(332), S(212)
        win = self.win = tk.Toplevel(app.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=T["bg"])
        cv = self.cv = tk.Canvas(win, width=w, height=h, bg=T["bg"], highlightthickness=0)
        cv.pack(fill="both", expand=True)
        round_rect(cv, S(1), S(1), w - S(1), h - S(1), S(16),
                   fill=T["card"], outline=T["stroke"], width=S(1))
        inner = tk.Frame(cv, bg=T["card"])
        cv.create_window((S(16), S(12)), window=inner, anchor="nw",
                         width=w - S(32), height=h - S(24))

        top = tk.Frame(inner, bg=T["card"])
        top.pack(anchor="w")
        tk.Label(top, text="⚠", bg=T["card"], fg=T["warn"],
                 font=(FONT, FS(15), "bold")).pack(side="left")
        tk.Label(top, text=f"  {app.t('warn_soon', w=self.word)}", bg=T["card"], fg=T["text"],
                 font=(FONT, FS(13), "bold")).pack(side="left")
        self.sub_lbl = tk.Label(inner, text="", bg=T["card"], fg=T["sub"],
                                font=(FONT, FS(10)), anchor="w")
        self.sub_lbl.pack(fill="x", pady=(S(6), 0))
        self.t_lbl = tk.Label(inner, text="", bg=T["card"], fg=T["danger"],
                              font=(FONT, FS(24), "bold"))
        self.t_lbl.pack(pady=S(2))
        brow = tk.Frame(inner, bg=T["card"])
        brow.pack(pady=(S(8), 0))
        Btn(brow, app, app.t("btn_wcancel"), self.do_cancel, w=S(94), h=S(34),
            style="danger", font_size=11).pack(side="left")
        Btn(brow, app, app.t("btn_postpone"), self.do_postpone, w=S(108), h=S(34),
            style="soft", font_size=11).pack(side="left", padx=S(8))
        Btn(brow, app, app.t("btn_ignore"), self.dismiss, w=S(66), h=S(34),
            style="ghost", font_size=11).pack(side="left")

        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        self.tx, self.ty = sw - w - S(28), sh - h - S(64)
        win.update_idletasks()
        win.geometry(f"{w}x{h}+{sw - w}+{sh}")
        self._slide(sw - w, sh, 0)
        self._px = self._py = 0
        for seq in ("<Button-1>", "<B1-Motion>"):
            pass
        win.bind("<Button-1>", self._press)
        win.bind("<B1-Motion>", self._drag)
        self._update()
        self._job = win.after(400, self._poll)

    def _press(self, e):
        self._px, self._py = e.x, e.y

    def _drag(self, e):
        self.tx = self.win.winfo_x() + e.x - self._px
        self.ty = self.win.winfo_y() + e.y - self._py
        self.win.geometry(f"+{self.tx}+{self.ty}")

    def _slide(self, x, y, i):
        n = 14
        yy = int(y + (self.ty - y) * (i / n))
        self.win.geometry(f"+{x}+{yy}")
        if i < n:
            self.win.after(12, self._slide, x, y, i + 1)

    def _update(self):
        t = self.app.task
        if t:
            self.sub_lbl.config(text=self.app.t(
                "warn_body", w=self.app.t("act_" + t["type"]), t=t["target"]))
        self.t_lbl.config(text=fmt_sec(self.remain))

    def _poll(self):
        t = self.app.task
        if not t or not t.get("warned"):
            self.dismiss()
            return
        self.remain = max(0, int(t["end"] - time.time() + 0.999))
        self._update()
        self._job = self.win.after(400, self._poll)

    def do_cancel(self):
        self.app.cancel()

    def do_postpone(self):
        self.app.postpone()

    def dismiss(self):
        try:
            self.win.after_cancel(self._job)
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        if self.app.warn_win is self:
            self.app.warn_win = None


# ---------------- 主程序 ----------------
class App:

    def __init__(self, root):
        self.root = root
        cfg = load_cfg()
        self.theme_auto = bool(cfg.get("theme_auto", False))
        self.theme_name = cfg.get("theme", "dark")
        if self.theme_auto:
            self.theme_name = "dark" if system_dark() else "light"
        if self.theme_name not in THEMES:
            self.theme_name = "dark"
        self.T = THEMES[self.theme_name]
        self.lang = cfg.get("lang", "zh") if cfg.get("lang") in LANGS else "zh"
        self.HINT = self.t("hint")
        self.state = dict(
            mode=cfg.get("mode", "cd"), ttype=cfg.get("ttype", "shutdown"),
            hh=str(cfg.get("hh", "23")), mm=str(cfg.get("mm", "30")),
            minutes=str(cfg.get("minutes", "30")),
            remind=bool(cfg.get("remind", True)), topmost=bool(cfg.get("topmost", False)),
            theme_auto=self.theme_auto,
            repeat=bool(cfg.get("repeat", False)),
            tray_on=bool(cfg.get("tray_on", True)),
        )
        self.repeat_conf = cfg.get("repeat_task") or None
        self.task = None
        self.warn_win = None
        self.tray = None
        self._flash_job = None
        self._tick_count = 0
        self.build()
        if self.state["topmost"]:
            root.attributes("-topmost", True)
        self.root.after(60, self.apply_chrome)
        self._start_tray()
        self._restore_repeat()
        self.tick()

    def t(self, key, **kw):
        """取当前语言的文案，缺漏时回退中文基准"""
        s = I18N[self.lang].get(key) or I18N["zh"][key]
        return s.format(**kw) if kw else s

    # ---------- 托盘 ----------
    def _start_tray(self):
        if not HAS_TRAY:
            self.tray = None
            return
        try:
            menu = pystray.Menu(
                pystray.MenuItem(self.t("tray_show"), self._tray_show, default=True),
                pystray.MenuItem(self.t("tray_exit"), self._tray_quit),
            )
            self.tray = pystray.Icon("shutdown-timer", tray_logo_image(),
                                     self.t("title"), menu)
            self.tray.run_detached()
        except Exception:
            self.tray = None

    def _stop_tray(self):
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass
            self.tray = None

    def _tray_show(self, icon=None, item=None):
        def _show():
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except Exception:
                pass
        self.root.after(0, _show)

    def _tray_quit(self, icon=None, item=None):
        self.root.after(0, self._real_exit)

    # ---------- 界面构建 ----------
    def mk(self, parent, text, size=10, key="sub", bold=False):
        return tk.Label(parent, text=text, bg=parent["bg"], fg=self.T[key],
                        font=(FONT, FS(size), "bold" if bold else "normal"))

    def make_entry(self, parent, width, vmax=None, decimal=False):
        T = self.T
        e = tk.Entry(parent, width=width, bg=T["entry"], fg=T["text"],
                     insertbackground=T["accent"], relief="flat", justify="center",
                     font=(FONT, FS(16), "bold"), highlightthickness=S(1),
                     highlightbackground=T["stroke"], highlightcolor=T["accent"],
                     selectbackground=T["accent"], selectforeground="#ffffff")
        vcmd = (self.root.register(lambda v: self._valid_input(v, vmax, decimal)), "%P")
        e.config(validate="key", validatecommand=vcmd)
        return e

    @staticmethod
    def _valid_input(v, vmax, decimal):
        """按键级输入校验：定时只能 0-23 / 0-59 两位数字；倒计时允许数字和小数点"""
        if v == "":
            return True
        if decimal:
            if v.count(".") > 1 or not all(c.isdigit() or c == "." for c in v):
                return False
            if len(v) > 7:
                return False
        elif not v.isdigit() or len(v) > 2:
            return False
        try:
            return vmax is None or float(v) <= vmax
        except ValueError:
            return False

    def build(self, recenter=True):
        T = self.T
        st = self.state
        self.HINT = self.t("hint")
        self.root.title("定时关机助手")
        self.root.configure(bg=T["bg"])
        self.root.resizable(False, False)

        self.main = tk.Frame(self.root, bg=T["bg"])
        self.main.pack(fill="both", expand=True, padx=S(20), pady=S(12))

        # ---- 顶栏 ----
        head = tk.Frame(self.main, bg=T["bg"])
        head.pack(fill="x")
        logo = tk.Canvas(head, width=S(36), height=S(36), bg=T["bg"], highlightthickness=0)
        logo.pack(side="left")
        round_rect(logo, S(2), S(2), S(34), S(34), S(11), fill=T["accent"])
        cx = S(18)
        logo.create_arc(S(10), S(10), S(26), S(26), start=-50, extent=262,
                        style="arc", outline="#ffffff", width=max(2, S(2)))
        logo.create_line(cx, S(8), cx, S(16), fill="#ffffff",
                         width=max(2, S(2)), capstyle="round")
        tit = tk.Frame(head, bg=T["bg"])
        tit.pack(side="left", padx=(S(10), 0))
        tk.Label(tit, text=self.t("title"), bg=T["bg"], fg=T["text"],
                 font=(FONT, FS(15), "bold")).pack(anchor="w")
        self.clock_lbl = tk.Label(tit, text="", bg=T["bg"], fg=T["sub"], font=(FONT, FS(10)))
        self.clock_lbl.pack(anchor="w")
        self.btn_top = IconBtn(head, self, icon_pin, self.toggle_top)
        self.btn_top.pack(side="right")
        self.btn_lang = IconBtn(head, self, icon_globe, self.toggle_language)
        self.btn_lang.pack(side="right")
        self.btn_theme = IconBtn(head, self,
                                 icon_sun if self.theme_name == "dark" else icon_moon,
                                 self.toggle_theme)
        self.btn_theme.pack(side="right", padx=(0, S(6)))
        self.btn_top.set_selected(st["topmost"])

        # ---- 进度环卡片 ----
        ring_card = Card(self.main, self, S(392), S(224))
        ring_card.pack(fill="x", pady=(S(12), 0))
        self.ring_cv = tk.Canvas(ring_card.inner, width=S(200), height=S(200),
                                 bg=T["card"], highlightthickness=0)
        self.ring_cv.pack()
        pad = S(18)
        self._ring_thick = S(13)
        self._ring_r = (S(200) - 2 * pad) / 2
        if HAS_PIL:
            self.ring_cv._track_ph = render_ring_photo(S(200), self._ring_thick, 0.0,
                                                       T["card2"], "", "", "", False)
            self.ring_cv.create_image(0, 0, image=self.ring_cv._track_ph, anchor="nw")
        else:
            self._ring_bbox = (pad, pad, S(200) - pad, S(200) - pad)
            self._arc_bg = self.ring_cv.create_arc(*self._ring_bbox, start=90, extent=359.9,
                                                   style="arc", outline=T["card2"],
                                                   width=self._ring_thick)
            self._arc = self.ring_cv.create_arc(*self._ring_bbox, start=90, extent=0,
                                                style="arc", outline=T["accent"],
                                                width=self._ring_thick)
        self._t_big = self.ring_cv.create_text(S(100), S(100) - S(12), text="--:--",
                                               font=(FONT, FS(28), "bold"), fill=T["text"])
        self._t_sub = self.ring_cv.create_text(S(100), S(100) + S(22), text="",
                                               font=(FONT, FS(10)), fill=T["sub"])

        # ---- 模式分段 ----
        self.seg = Segmented(self.main, self, [("cd", self.t("mode_cd")),
                                               ("at", self.t("mode_at"))],
                             self.set_mode, w=S(392))
        self.seg.pack(fill="x", pady=(S(12), 0))

        # ---- 参数面板 ----
        self.panel_box = tk.Frame(self.main, bg=T["bg"], height=S(50))
        self.panel_box.pack(fill="x", pady=(S(12), 0))
        self.panel_box.pack_propagate(False)

        self.p_cd = tk.Frame(self.panel_box, bg=T["bg"])
        self.e_min = self.make_entry(self.p_cd, 6, vmax=5256000, decimal=True)
        self.e_min.pack(side="left", ipady=S(7))
        self.mk(self.p_cd, self.t("unit_min_after"), 11).pack(side="left")
        quick = tk.Frame(self.p_cd, bg=T["bg"])
        quick.pack(side="right")
        for m in (15, 30, 60, 120):
            Chip(quick, self, str(m), lambda v=m: self._quick_min(v), w=S(56)).pack(side="left", padx=(S(6), 0))

        self.p_at = tk.Frame(self.panel_box, bg=T["bg"])
        self.e_h = self.make_entry(self.p_at, 4, vmax=23)
        self.e_h.pack(side="left", ipady=S(7))
        self.mk(self.p_at, self.t("unit_h"), 11).pack(side="left")
        self.e_m = self.make_entry(self.p_at, 4, vmax=59)
        self.e_m.pack(side="left", ipady=S(7))
        self.mk(self.p_at, self.t("unit_m"), 11).pack(side="left")
        quick2 = tk.Frame(self.p_at, bg=T["bg"])
        quick2.pack(side="right")
        Chip(quick2, self, self.t("plus1h"), lambda: self._quick_hours(1), w=S(76)).pack(side="left", padx=(S(6), 0))
        Chip(quick2, self, self.t("plus2h"), lambda: self._quick_hours(2), w=S(76)).pack(side="left", padx=(S(6), 0))

        self.e_min.insert(0, st["minutes"])
        self.e_h.insert(0, st["hh"])
        self.e_m.insert(0, st["mm"])

        # ---- 任务类型 ----
        trow = tk.Frame(self.main, bg=T["bg"])
        trow.pack(fill="x", pady=(S(12), 0))
        self.mk(trow, self.t("task_lbl"), 11).pack(side="left")
        tf = tk.Frame(trow, bg=T["bg"])
        tf.pack(side="left", padx=S(14))
        self.type_chips = {}
        for key in ("shutdown", "restart", "sleep"):
            ch = Chip(tf, self, self.t("act_" + key), lambda k=key: self.set_type(k), w=S(96))
            ch.pack(side="left", padx=(0, S(8)))
            self.type_chips[key] = ch

        # ---- 提醒开关 ----
        rrow = tk.Frame(self.main, bg=T["bg"])
        rrow.pack(fill="x", pady=(S(10), 0))
        self.mk(rrow, self.t("remind_lbl"), 10.5).pack(side="left")
        self.sw_remind = Switch(rrow, self, init=st["remind"])
        self.sw_remind.pack(side="right")

        # ---- 每日重复 / 系统主题 / 托盘 ----
        row_rep = tk.Frame(self.main, bg=T["bg"])
        self.mk(row_rep, self.t("repeat_lbl"), 10.5).pack(side="left")
        self.sw_repeat = Switch(row_rep, self, init=st["repeat"])
        self.sw_repeat.pack(side="right")
        row_rep.pack(fill="x", pady=(S(6), 0))

        row_auto = tk.Frame(self.main, bg=T["bg"])
        self.mk(row_auto, self.t("auto_lbl"), 10.5).pack(side="left")
        self.sw_auto = Switch(row_auto, self, init=st["theme_auto"],
                              command=lambda v: self._auto_theme_toggled(v))
        self.sw_auto.pack(side="right")
        row_auto.pack(fill="x", pady=(S(6), 0))

        if HAS_TRAY:
            row_tray = tk.Frame(self.main, bg=T["bg"])
            self.mk(row_tray, self.t("tray_lbl"), 10.5).pack(side="left")
            self.sw_tray = Switch(row_tray, self, init=st["tray_on"],
                                  command=lambda v: self._tray_toggled(v))
            self.sw_tray.pack(side="right")
            row_tray.pack(fill="x", pady=(S(6), 0))

        # ---- 主按钮 ----
        self.btn_start = Btn(self.main, self, self.t("btn_start"), self.start,
                             w=S(392), h=S(46), style="solid")
        self.btn_start.pack(fill="x", pady=(S(14), 0))
        self.btn_cancel = Btn(self.main, self, self.t("btn_cancel"), self.cancel,
                              w=S(392), h=S(40), style="ghost")
        self.btn_cancel.pack(fill="x", pady=(S(8), 0))

        self.msg_lbl = tk.Label(self.main, text=self.HINT, bg=T["bg"], fg=T["sub"],
                                font=(FONT, FS(10)), wraplength=S(380), justify="center")
        self.msg_lbl.pack(pady=(S(6), 0))
        tk.Label(self.main, text="风好大 制作", bg=T["bg"], fg=T["faint"],
                 font=(FONT, FS(9))).pack()

        # ---- 恢复上次状态 ----
        self.mode = st["mode"]
        self.ttype = st["ttype"]
        self.seg.select(self.mode, fire=False)
        (self.p_at if self.mode == "at" else self.p_cd).pack(fill="both", expand=True)
        self.set_type(self.ttype)
        self.draw_idle()

        # 窗口自适应内容；recenter=False 时保持当前位置（主题切换用）
        self.root.update_idletasks()
        w = self.main.winfo_reqwidth() + S(40)
        h = self.main.winfo_reqheight() + S(26)
        if recenter:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
        else:
            self.root.geometry(f"{w}x{h}")

    def apply_chrome(self):
        """标题栏与边框跟随主题（Win11 上标题栏融入背景，Win10 退化为深/浅标题栏）"""
        if not IS_WIN:
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            dark = 1 if self.theme_name == "dark" else 0
            for attr in (20, 19):
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(ctypes.c_int(dark)), 4) == 0:
                    break

            def cref(hx):
                hx = hx.lstrip("#")
                r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
                return r | (g << 8) | (b << 16)

            for attr in (35, 34):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(ctypes.c_int(cref(self.T["bg"]))), 4)
        except Exception:
            pass

    # ---------- 交互 ----------
    def set_mode(self, key):
        self.mode = key
        self.seg.select(key, fire=False)
        if key == "at":
            self.p_cd.pack_forget()
            self.p_at.pack(fill="both", expand=True)
        else:
            self.p_at.pack_forget()
            self.p_cd.pack(fill="both", expand=True)

    def set_type(self, key):
        self.ttype = key
        for k, ch in self.type_chips.items():
            ch.set_selected(k == key)

    def _quick_min(self, m):
        self.e_min.delete(0, "end")
        self.e_min.insert(0, str(m))
        self.flash(self.t("quick_filled", v=f"{m} {self.t('unit_min_after').strip()}"), "sub")

    def _quick_hours(self, hcount):
        t = datetime.datetime.now() + datetime.timedelta(hours=hcount)
        self.set_mode("at")
        self.e_h.delete(0, "end")
        self.e_h.insert(0, f"{t.hour:02d}")
        self.e_m.delete(0, "end")
        self.e_m.insert(0, f"{t.minute:02d}")
        self.flash(self.t("quick_filled", v=f"{t.hour:02d}:{t.minute:02d}"), "sub")

    def toggle_language(self):
        nxt = LANGS[(LANGS.index(self.lang) + 1) % len(LANGS)]
        self.collect()
        self.lang = nxt
        self.save_state()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        topmost = self.btn_top.sel
        self.main.destroy()
        self.build(recenter=False)
        self.root.geometry(f"+{px}+{py}")
        self.apply_chrome()
        self.root.lift()
        self.root.focus_force()
        if topmost:
            self.root.attributes("-topmost", True)
        self.tick()
        self.flash(self.t("lang_set", n=LANG_NAME[nxt]), "ok")

    def toggle_top(self):
        v = not self.btn_top.sel
        self.btn_top.set_selected(v)
        self.root.attributes("-topmost", v)

    def toggle_theme(self):
        """手动切换主题：同时关闭「跟随系统」"""
        if self.sw_auto.winfo_exists() and self.sw_auto.value:
            self.sw_auto.set(False)
            self.state["theme_auto"] = False
        target = "light" if self.theme_name == "dark" else "dark"
        self._switch_theme(target)

    def _auto_theme_toggled(self, v):
        self.state["theme_auto"] = v
        if v:
            self._follow_system()
        self.save_state()

    def _follow_system(self):
        want = "dark" if system_dark() else "light"
        if want != self.theme_name:
            self._switch_theme(want)

    def _switch_theme(self, name):
        self.collect()
        self.theme_name = name
        self.T = THEMES[name]
        px, py = self.root.winfo_x(), self.root.winfo_y()
        topmost = self.btn_top.sel
        self.main.destroy()
        self.build(recenter=False)
        self.root.geometry(f"+{px}+{py}")
        self.apply_chrome()
        self.root.lift()
        self.root.focus_force()
        if topmost:
            self.root.attributes("-topmost", True)
        self.tick()

    def _tray_toggled(self, v):
        self.state["tray_on"] = v
        self.save_state()

    # ---------- 每日重复任务 ----------
    def _schedule_repeat(self, quiet=False):
        """按 repeat_conf 安排下一次（今天或明天）的定时任务"""
        rc = self.repeat_conf
        if not rc:
            return
        now = datetime.datetime.now()
        try:
            target = now.replace(hour=int(rc["hh"]), minute=int(rc["mm"]),
                                 second=0, microsecond=0)
        except (ValueError, KeyError):
            return
        if target <= now:
            target += datetime.timedelta(days=1)
        sec = max(5, int((target - now).total_seconds()))
        ttype = rc.get("type", "shutdown")
        word = self.t("act_" + ttype)
        if ttype in FLAG:
            if self.task and self.task.get("sys"):
                run_cmd(["shutdown", "/a"])
            if not run_cmd(["shutdown", FLAG[ttype], "/t", str(sec)]):
                return self.flash(self.t("err_admin"), "danger")
            self.task = dict(type=ttype, end=time.time() + sec, total=sec,
                             target=target.strftime("%H:%M"), warned=False,
                             sys=True, repeat=True)
        else:
            self.task = dict(type=ttype, end=time.time() + sec, total=sec,
                             target=target.strftime("%H:%M"), warned=False,
                             sys=False, repeat=True)
        if not quiet:
            self.flash(self.t("repeat_ok", t=target.strftime("%H:%M"), w=word), "ok")

    def _restore_repeat(self):
        """启动时恢复上次的每日重复任务"""
        if self.repeat_conf and self.state.get("repeat"):
            self._schedule_repeat(quiet=True)

    def _reschedule_after_done(self, t):
        """重复任务执行完毕后，自动安排明天的同一任务"""
        self._schedule_repeat()

    FLASH_MARK = {"ok": "✓  ", "warn": "⚠  ", "danger": "✕  "}

    def flash(self, msg, kind="sub"):
        if not self.msg_lbl.winfo_exists():
            return
        self.msg_lbl.config(text=self.FLASH_MARK.get(kind, "") + msg,
                            fg=self.T.get(kind, self.T["sub"]))
        if self._flash_job:
            try:
                self.root.after_cancel(self._flash_job)
            except Exception:
                pass
        self._flash_job = self.root.after(4000, self._reset_hint)

    def _reset_hint(self):
        if self.msg_lbl.winfo_exists():
            self.msg_lbl.config(text=self.HINT, fg=self.T["sub"])

    # ---------- 核心逻辑 ----------
    def start(self):
        if self.mode == "at":
            try:
                hh, mm = int(self.e_h.get()), int(self.e_m.get())
            except ValueError:
                return self.flash(self.t("err_time_invalid"), "danger")
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                return self.flash(self.t("err_time_range"), "danger")
            now = datetime.datetime.now()
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if target <= now:
                return self.flash(self.t("err_time_past"), "danger")
            sec = max(1, int((target - now).total_seconds()))
            target_str = f"{hh:02d}:{mm:02d}"
        else:
            try:
                minutes = float(self.e_min.get())
            except ValueError:
                return self.flash(self.t("err_minutes_invalid"), "danger")
            if minutes <= 0:
                return self.flash(self.t("err_minutes_positive"), "danger")
            sec = max(5, int(round(minutes * 60)))
            target_str = (datetime.datetime.now() +
                          datetime.timedelta(seconds=sec)).strftime("%H:%M")

        word = self.t("act_" + self.ttype)
        task = dict(type=self.ttype, end=time.time() + sec, total=sec,
                    target=target_str, warned=False)
        if self.mode == "at" and self.sw_repeat.value:
            task["repeat"] = True
            self.repeat_conf = {"type": self.ttype, "hh": f"{hh:02d}", "mm": f"{mm:02d}"}
        if self.ttype in FLAG:
            if self.task and self.task.get("sys"):
                run_cmd(["shutdown", "/a"])
            if not run_cmd(["shutdown", FLAG[self.ttype], "/t", str(sec)]):
                return self.flash(self.t("err_admin"), "danger")
            task["sys"] = True
            self.task = task
            tip = ""
        else:
            task["sys"] = False
            self.task = task
            tip = self.t("sleep_tip")
        self.close_warn()
        self.flash(self.t("ok_set", t=target_str, w=word) + tip, "ok")

    def cancel(self):
        if not self.task:
            return self.flash(self.t("err_no_task"), "warn")
        t = self.task
        self.task = None
        self.repeat_conf = None
        self.close_warn()
        if t["sys"]:
            ok = run_cmd(["shutdown", "/a"])
            self.flash(self.t("ok_cancel") if ok else self.t("err_cancel_fail"),
                       "ok" if ok else "warn")
        else:
            self.flash(self.t("ok_cancel_sleep"), "ok")

    def postpone(self):
        t = self.task
        if not t:
            return
        if t["sys"]:
            run_cmd(["shutdown", "/a"])
            if not run_cmd(["shutdown", FLAG[t["type"]], "/t", "600"]):
                return self.flash(self.t("err_postpone_fail"), "danger")
        t["end"] = time.time() + 600
        t["total"] = 600
        t["warned"] = False
        t["target"] = (datetime.datetime.now() +
                       datetime.timedelta(minutes=10)).strftime("%H:%M")
        self.close_warn()
        self.flash(self.t("ok_postpone"), "ok")

    def close_warn(self):
        if self.warn_win is not None:
            self.warn_win.dismiss()
            self.warn_win = None

    def show_warn(self, remain):
        self.close_warn()
        self.warn_win = WarnWindow(self, remain)

    def remind_on(self):
        try:
            return self.sw_remind.value
        except Exception:
            return True

    # ---------- 界面刷新 ----------
    def draw_ring(self, frac, big, small, danger=False, big_size=28):
        """进度环：渐变弧 + 圆头端点；danger 时切换警示单色"""
        cv = self.ring_cv
        if not cv.winfo_exists():
            return
        T = self.T
        cv.delete("prog")
        frac = clamp(frac, 0.0, 1.0)
        if HAS_PIL:
            if frac > 0.003:
                cv._prog_ph = render_ring_photo(S(200), self._ring_thick, frac,
                                                T["card2"], T["accent"], "#8b5cf6",
                                                T["danger"], danger)
                cv.create_image(0, 0, image=cv._prog_ph, anchor="nw", tags="prog")
        elif frac > 0.003:
            total = 359.9 * frac
            if danger:
                cv.itemconfig(self._arc, extent=-total, outline=T["danger"])
            else:
                cv.itemconfig(self._arc, extent=-total, outline=T["accent"])
        cv.itemconfig(self._t_big, text=big, fill=T["text"],
                      font=(FONT, FS(big_size), "bold"))
        cv.itemconfig(self._t_sub, text=small, fill=T["sub"])

    def draw_idle(self):
        """空闲态：环完全空掉（弧 = 任务进度，不能挪作他用），中央显示当前时间作参考"""
        now = datetime.datetime.now()
        self.draw_ring(0.0, now.strftime("%H:%M:%S"), self.t("idle_sub"), big_size=26)

    def tick(self):
        self._tick_count += 1
        if self.state.get("theme_auto") and self._tick_count % 15 == 0:
            want = "dark" if system_dark() else "light"
            if want != self.theme_name:
                self._follow_system()
                return
        now = datetime.datetime.now()
        try:
            if not self.clock_lbl.winfo_exists():
                return
        except Exception:
            return
        self.clock_lbl.config(text=now.strftime(self.t("date_fmt") + " · ")
                              + self.t("wd")[now.weekday()])
        if self.task:
            t = self.task
            remain = int(t["end"] - time.time() + 0.999)
            word = self.t("act_" + t["type"])
            if remain > 0:
                frac = remain / max(1, t["total"])
                self.draw_ring(frac, fmt_sec(remain), f"{t['target']} {word}",
                               danger=remain <= 60)
                if remain <= 60 and not t["warned"] and self.remind_on():
                    t["warned"] = True
                    self.show_warn(remain)
            else:
                if t["sys"]:
                    if t.get("repeat") and remain <= -5:
                        # 系统已执行完毕，自动安排明天的同一任务
                        self._schedule_repeat()
                    if self.task is t and remain > -20 and not t.get("repeat"):
                        self.draw_ring(0.0, self.t("executing"),
                                       f"{t['target']} {word}")
                    elif self.task is not t:
                        self.draw_idle()
                else:
                    ok = run_cmd(["shutdown", "/h"])
                    self.flash(self.t("ok_slept") if ok else self.t("err_sleep_fail"),
                               "ok" if ok else "danger")
                    if t.get("repeat"):
                        self._schedule_repeat(quiet=not ok)
                    else:
                        self.task = None
                        self.draw_idle()
        else:
            self.draw_idle()
        self.root.after(200, self.tick)

    # ---------- 状态与配置 ----------
    def collect(self):
        try:
            self.state.update(
                mode=self.mode, ttype=self.ttype,
                hh=self.e_h.get().strip() or "23", mm=self.e_m.get().strip() or "30",
                minutes=self.e_min.get().strip() or "30",
                remind=self.sw_remind.value, topmost=self.btn_top.sel,
                repeat=self.sw_repeat.value,
            )
        except Exception:
            pass

    def save_state(self):
        self.collect()
        try:
            os.makedirs(CFG_DIR, exist_ok=True)
            data = dict(self.state)
            data["theme"] = self.theme_name
            data["lang"] = self.lang
            data["repeat_task"] = self.repeat_conf or None
            with open(CFG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def on_close(self):
        """点关闭 / Alt+F4：开着托盘开关时隐藏到托盘，否则真实退出"""
        if HAS_TRAY and self.tray is not None and self.state.get("tray_on"):
            self.root.withdraw()
            try:
                self.tray.notify(self.t("tray_tip"), self.t("title"))
            except Exception:
                pass
            return
        self._real_exit()

    def _real_exit(self):
        if self.task and not self.task["sys"]:
            if not messagebox.askyesno(self.t("close_title"), self.t("close_body"),
                                       icon="warning"):
                return
        self.save_state()
        self._stop_tray()
        self.root.destroy()


def main():
    root = tk.Tk()
    icon = ensure_app_icon()
    if icon:
        try:
            root.iconbitmap(default=icon)
        except Exception:
            pass
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
