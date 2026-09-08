.PHONY: setup check profile research look proto-check showcase build image verify clean

setup:          ## разовая установка окружения: питон, зависимости, браузер
	bash ядро/скрипты/setup.sh

check:          ## самопроверка: всё ли на месте и открывается ли браузер
	.venv/bin/python ядро/скрипты/selftest.py

profile:        ## показать профили и кто из них активный
	.venv/bin/python ядро/скрипты/профиль.py --список

research:       ## ресёрч ниши: make research WORK=сайты/моё-дело URLS="https://a.ru https://b.ru"
	.venv/bin/python ядро/скрипты/ресёрч_ниши.py $(URLS) --работа $(WORK)

## Экраны и замеры лягут в сайты/_референсы/<имя сайта>/. Чтобы положить их в папку работы,
## запустите скрипт напрямую: посмотреть_сайт.py <ссылка> --куда сайты/<имя>/референсы/<чужой>/
## — по папке на каждый референс, иначе второй затрёт замеры первого.
look:           ## посмотреть чужой сайт: make look URL=https://пример.ru
	.venv/bin/python ядро/скрипты/посмотреть_сайт.py $(URL)

## Скрипт считает форму: пресет и число экранов, гейт, кнопки, цифры без источника, стоп-слова.
## Смысл — одно ли обещание, нарастает ли аргументация — читается глазами по ядро/прототип.md.
proto-check:    ## проверить прототип перед вёрсткой: make proto-check PROTO=сайты/моё-дело/прототип.md
	@test -n "$(PROTO)" || { echo "Укажите файл прототипа: make proto-check PROTO=сайты/моё-дело/прототип.md"; exit 2; }
	.venv/bin/python ядро/скрипты/проверить_прототип.py $(PROTO)

showcase:       ## витрина вариантов: make showcase WORK=сайты/моё-дело
	.venv/bin/python ядро/скрипты/витрина.py $(WORK)

build:          ## собрать и показать: make build WORK=сайты/моё-дело [SCREEN=1]
	.venv/bin/python ядро/скрипты/собрать.py $(WORK) $(if $(SCREEN),--экран $(SCREEN))

image:          ## вставить и сжать картинку: make image FILE=фото.jpg WORK=сайты/моё-дело
	@test -n "$(WORK)" || { echo "Укажите папку работы: make image FILE=фото.jpg WORK=сайты/моё-дело"; exit 2; }
	.venv/bin/python ядро/скрипты/картинка.py $(FILE) --куда $(WORK)/img

verify:         ## проверить свой сайт: make verify SITE=сайты/моё-дело/сайт
	.venv/bin/python ядро/скрипты/проверить.py $(SITE)

clean:          ## убрать следы самопроверки (профили и ваши сайты не трогаем)
	rm -rf сайты/_самопроверка
