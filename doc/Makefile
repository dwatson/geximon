all: geximon.html geximon.txt

geximon.html: geximon-C.xml
	db2html --nochunks geximon-C.xml
	mv geximon-C/geximon-C.html geximon.html
	rm -rf geximon-C/ geximon-C.junk/

geximon.txt: geximon.html
	lynx -dump geximon.html > geximon.txt

clean:
	rm -f geximon.txt geximon.html
