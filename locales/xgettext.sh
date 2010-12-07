xgettext -L Python -f locales/files.txt -o locales/messages.pot
msgmerge -N locales/it.po locales/messages.pot -o locales/it.po
