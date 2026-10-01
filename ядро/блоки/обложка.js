// Обложка с видео. Свой ролик у телефона и у компьютера: data-ролик-телефон / data-ролик-компьютер и их постеры
// data-постер-…; адрес ставит скрипт по ширине окна — каждый размер качает только свой файл. Старая пара (<source> +
// data-телефон) работает как раньше. Звука нет никогда: muted + playsinline, иначе iPhone не заиграет. Запасной кадр —
// постер ЭТОГО ЖЕ ролика (класс картинка--постер стоит в разметке и снимается, когда ролик пошёл; нет JS — виден постер).
// Автозапуск отклонён (встроенный браузер мессенджера, энергосбережение) — ролик стартует по первому касанию или прокрутке.
// При reduced-motion и в Safari без альфа-VP9 у живого портрета — только постер.
(function () {
  var видео = document.querySelector(".первый-экран__картинка video");
  if (!видео) { return; }
  var фигура = видео.closest(".картинка"), ua = navigator.userAgent, узко = matchMedia("(max-width: 899px)");
  var тихо = matchMedia("(prefers-reduced-motion: reduce)").matches, кадр = фигура.querySelector("img");
  var сафари = /safari/i.test(ua) && !/chrome|chromium|crios|android|edg/i.test(ua), ждём = false;
  var альфа = фигура.classList.contains("картинка--живой-портрет"), жесты = ["touchstart", "pointerdown", "click", "scroll", "keydown"];
  function постер() { видео.pause(); видео.removeAttribute("autoplay"); фигура.classList.add("картинка--постер"); }
  function пошло() { фигура.classList.remove("картинка--постер"); }
  function поЖесту() { жесты.forEach(function (и) { removeEventListener(и, поЖесту, true); }); ждём = false; пуск(); }
  function отказ() { постер(); if (ждём) { return; } ждём = true; жесты.forEach(function (и) { addEventListener(и, поЖесту, { capture: true, passive: true }); }); }
  function пуск() { var о; try { о = видео.play(); } catch (е) { о = null; } if (о && о.then) { о.then(пошло, отказ); } }
  function выбрать() {   // новый способ: адрес только у своего размера
    var вид = узко.matches ? "телефон" : "компьютер", адрес = видео.getAttribute("data-ролик-" + вид);
    if (видео.getAttribute("data-вид") === вид) { return false; }
    видео.setAttribute("data-вид", вид); видео.muted = true; видео.setAttribute("playsinline", "");
    видео.poster = видео.getAttribute("data-постер-" + вид) || видео.poster;
    if (!адрес || тихо) { постер(); return false; }
    видео.src = адрес; видео.load(); return true;
  }
  var новый = видео.hasAttribute("data-ролик-телефон") || видео.hasAttribute("data-ролик-компьютер");
  if (!новый && узко.matches && видео.getAttribute("data-телефон")) {
    видео.setAttribute("poster", видео.getAttribute("data-телефон-постер") || видео.getAttribute("poster"));
    if (кадр) { кадр.src = видео.getAttribute("poster"); }
    видео.src = видео.getAttribute("data-телефон"); видео.load();   // src элемента сильнее <source>: иначе браузер с WebM оставит горизонтальный ролик
  }
  if (тихо) { document.querySelectorAll(".первый-экран__картинка video").forEach(function (в) { в.pause(); в.removeAttribute("autoplay"); }); }
  if (тихо || (альфа && (сафари || !видео.canPlayType('video/webm; codecs="vp9"')))) { постер(); return; }
  видео.addEventListener("error", постер, true);
  if (!новый) { var обещание = видео.play(); if (обещание && обещание.catch) { обещание.then(пошло).catch(отказ); } return; }
  if (выбрать()) { пуск(); }
  if (узко.addEventListener) { узко.addEventListener("change", function () { if (выбрать()) { пуск(); } }); }
})();
