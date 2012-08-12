default:
	$(warning Choose extract, init, or update!)

extract:
	pybabel extract -F dtg/dtg.babelconfig -o dtg/translations/messages.pot dtg

update: extract
	pybabel update -i dtg/translations/messages.pot -d dtg/translations

init:
	echo Initing ${LANG} ...
	pybabel init -i dtg/translations/messages.pot -d dtg/translations -l ${LANG}


