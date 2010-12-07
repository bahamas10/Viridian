rm -f locales/it/LC_MESSAGES/viridian.mo
mkdir -p locales/it/LC_MESSAGES/
msgfmt -o locales/it/LC_MESSAGES/viridian.mo locales/it.po
