.PHONY: setup check profile look verify clean

setup:          ## разовая установка окружения: питон, зависимости, браузер
	bash ядро/скрипты/setup.sh

check:          ## самопроверка: всё ли на месте и открывается ли браузер
	.venv/bin/python ядро/скрипты/selftest.py

profile:        ## показать профили и кто из них активный
	.venv/bin/python ядро/скрипты/профиль.py --список

look:           ## посмотреть чужой сайт: make look URL=https://пример.ru
	.venv/bin/python ядро/скрипты/посмотреть_сайт.py $(URL)

verify:         ## проверить свой сайт: make verify SITE=сайты/моё-дело/сайт
	.venv/bin/python ядро/скрипты/проверить.py $(SITE)

clean:          ## убрать следы самопроверки (профили и ваши сайты не трогаем)
	rm -rf сайты/_самопроверка
