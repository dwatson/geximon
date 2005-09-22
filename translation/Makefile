extract:
	pygettext2.3 -o geximon.pot ../geximon/*.py
	for f in `ls *.po`; do			\
		msgmerge -U $$f geximon.pot ;	\
	done

compile:
	for f in `ls *.po`; do			\
		msgfmt -o $${f%.po}.mo $$f ;	\
	done
