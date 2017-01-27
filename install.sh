#!/bin/sh

TEMP_CRONTAB_FILE=$(mktemp crontab.XXXXXX)
EARTHPORN_PATH=`realpath $(dirname $0)`
MINUTE=`shuf -en 1 $(seq 0 59)`
HOURS=3

if crontab -l > $TEMP_CRONTAB_FILE; then
	if ! grep -E "earthporn\.py\$" $TEMP_CRONTAB_FILE > /dev/null; then
		echo "$MINUTE */$HOURS * * * cd $EARTHPORN_PATH && $EARTHPORN_PATH/earthporn.py" >> $TEMP_CRONTAB_FILE;
		crontab $TEMP_CRONTAB_FILE;
	fi
else
	echo "$MINUTE */$HOURS * * * cd $EARTHPORN_PATH && $EARTHPORN_PATH/earthporn.py" | crontab -;
fi

rm -f $TEMP_CRONTAB_FILE
