import locale
import os

# Run the tests in English whatever the desktop language is. cinnamon_clipboard.i18n picks
# the language once, on first import, so this has to happen before any test module imports it.
os.environ["LANGUAGE"] = "en"
os.environ["LC_ALL"] = "C.UTF-8"
locale.setlocale(locale.LC_ALL, "C.UTF-8")
