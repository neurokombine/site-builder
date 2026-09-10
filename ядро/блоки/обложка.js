// Обложка с видео. На телефоне — вертикальный ролик из data-телефон; при reduced-motion, в Safari без альфа-VP9 и при
// отказе play() — постер вместо видео (класс картинка--постер). Звука нет никогда: muted + playsinline, иначе iPhone не заиграет.
(function () {
  var видео = document.querySelector(".первый-экран__картинка video");
  if (!видео) { return; }
  var фигура = видео.closest(".картинка"), ua = navigator.userAgent;
  var телефон = matchMedia("(max-width: 899px)").matches, тихо = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var сафари = /safari/i.test(ua) && !/chrome|chromium|crios|android|edg/i.test(ua);
  var альфа = фигура.classList.contains("картинка--живой-портрет");
  function постер() { видео.pause(); видео.removeAttribute("autoplay"); фигура.classList.add("картинка--постер"); }
  if (телефон && видео.getAttribute("data-телефон")) {
    видео.setAttribute("poster", видео.getAttribute("data-телефон-постер") || видео.getAttribute("poster"));
    var кадр = фигура.querySelector("img");
    if (кадр) { кадр.src = видео.getAttribute("poster"); }
    видео.src = видео.getAttribute("data-телефон"); видео.load();   // src элемента сильнее <source>: иначе браузер с WebM оставит горизонтальный ролик
  }
  if (тихо) { document.querySelectorAll(".первый-экран__картинка video").forEach(function (в) { в.pause(); в.removeAttribute("autoplay"); }); }
  if (тихо || (альфа && (сафари || !видео.canPlayType('video/webm; codecs="vp9"')))) { постер(); return; }
  видео.addEventListener("error", постер, true);
  var обещание = видео.play();
  if (обещание && обещание.catch) { обещание.catch(постер); }
})();
