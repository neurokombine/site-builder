// Ролик обложки (ядро/картинки.md § 7). autoplay muted playsinline webkit-playsinline preload — в разметке; здесь: адрес
// по ширине окна (data-ролик-телефон / -компьютер, постеры data-постер-…; старая пара <source> + data-телефон работает),
// muted свойством до каждого play(), play() после адреса, на loadedmetadata/canplay, visibilitychange/pageshow и по
// первому касанию или прокрутке. Не пошёл за 1 с (отказ, вечное обещание, suspend/stalled, ошибка файла) — на месте
// постера анимированная картинка того же клипа: data-анимация-avif / -webp на img (у живой обложки с хвостом -телефон /
// -компьютер), AVIF через <source type="image/avif">, не открылся — WebP, не открылся и он — постер (картинка--постер).
// Пошёл позже — ролик возвращается; движение — по времени ролика, не по playing. reduced-motion — постер; живой
// портрет в Safari и без альфа-VP9 — сразу картинка с прозрачностью.
(function () {
  var ролики = [].slice.call(document.querySelectorAll(".первый-экран__картинка video"));
  if (!ролики.length) { return; }
  var узко = matchMedia("(max-width: 899px)"), тихо = matchMedia("(prefers-reduced-motion: reduce)").matches, ua = navigator.userAgent;
  var сафари = /safari/i.test(ua) && !/chrome|chromium|crios|android|edg/i.test(ua), ждём = false, ЖДАТЬ_МС = 1000;
  var жесты = ["touchstart", "pointerdown", "click", "scroll", "keydown"], АНИМ = "img[data-анимация-webp], img[data-анимация-webp-телефон], img[data-анимация-webp-компьютер]";
  function вид() { return узко.matches ? "телефон" : "компьютер"; }
  function адрес(img, ф) { return img.getAttribute("data-анимация-" + ф + "-" + вид()) || img.getAttribute("data-анимация-" + ф) || ""; }
  var все = ролики.map(function (в) {
    var фигура = в.closest(".картинка") || в.parentNode, один = фигура.querySelectorAll("video").length === 1;
    var с = {в: в, img: в.parentNode.querySelector(АНИМ) || (один ? фигура.querySelector("img") : null), играет: false, заменён: false, сломана: false,
             альфа: фигура.classList.contains("картинка--живой-портрет") && (сафари || !в.canPlayType('video/webm; codecs="vp9"'))};
    с.постер = function (да) { if (один) { фигура.classList.toggle("картинка--постер", да); } };
    с.пуск = function () {
      if (с.играет || с.альфа || тихо || !(в.currentSrc || в.src || в.querySelector("source"))) { return; }
      в.muted = true; в.defaultMuted = true; в.setAttribute("muted", "");
      var о; try { о = в.play(); } catch (е) { о = null; }
      if (о && о.catch) { о.catch(function () { с.запасной(); ждатьЖеста(); }); }
    };
    с.запасной = function () {
      clearTimeout(с.таймер);
      if (с.играет || тихо) { return; }
      с.постер(true);
      var img = с.img, avif = img && адрес(img, "avif"), webp = img && адрес(img, "webp"), рамка = img && img.parentNode;
      if (с.заменён || с.сломана || !(avif || webp)) { return; }
      var картинка = рамка.tagName === "PICTURE" ? рамка : null;
      с.было = {src: img.getAttribute("src"), скрыта: img.hidden, источники: картинка ? [].slice.call(картинка.querySelectorAll("source")) : []};
      с.было.источники.forEach(function (и) { картинка.removeChild(и); });
      if (картинка && avif) { с.источник = document.createElement("source"); с.источник.type = "image/avif"; с.источник.srcset = avif; картинка.insertBefore(с.источник, img); }
      img.onerror = function () {   // AVIF не открылся — WebP; и он не открылся — постер того же ролика, а не битая картинка
        if (с.источник && webp) { картинка.removeChild(с.источник); с.источник = null; if (img.getAttribute("src") !== webp) { img.src = webp; } return; }
        с.сломана = true; с.вернуть(); с.постер(true);
      };
      img.src = webp || avif; img.hidden = false; с.заменён = true;
    };
    с.вернуть = function () {   // картинка — обратно в постер из разметки
      var img = с.img, было = с.было;
      с.заменён = false;
      if (!было) { return; }
      img.onerror = null;
      if (с.источник && с.источник.parentNode) { с.источник.parentNode.removeChild(с.источник); }
      было.источники.forEach(function (и) { img.parentNode.insertBefore(и, img); });
      if (было.src === null) { img.removeAttribute("src"); } else { img.setAttribute("src", было.src); }
      img.hidden = было.скрыта; с.было = с.источник = null;
    };
    с.ждать = function () { clearTimeout(с.таймер); с.таймер = setTimeout(с.запасной, ЖДАТЬ_МС); с.пуск(); };
    с.выбрать = function () {   // адрес только у своего размера: другой размер свой файл не качает
      var размер = вид(), путь = в.getAttribute("data-ролик-" + размер);
      if (в.getAttribute("data-вид") === размер) { return; }
      в.setAttribute("data-вид", размер); с.вернуть(); с.играет = false; с.сломана = false;
      в.poster = в.getAttribute("data-постер-" + размер) || в.poster;
      if (!путь || тихо) { с.постер(true); return; }
      в.src = путь; с.ждать();
    };
    в.addEventListener("timeupdate", function () { if (в.currentTime > 0.05 && !в.paused && !с.играет) { с.играет = true; clearTimeout(с.таймер); с.вернуть(); с.постер(false); } });
    ["loadedmetadata", "canplay"].forEach(function (и) { в.addEventListener(и, с.пуск); });
    ["suspend", "stalled"].forEach(function (и) { в.addEventListener(и, function () { if (!с.играет && в.paused && (в.currentSrc || в.src)) { с.запасной(); } }); });
    в.addEventListener("error", с.запасной, true);   // true — ошибку <source> слышно только так
    return с;
  });
  function ждатьЖеста() { if (!ждём) { ждём = true; жесты.forEach(function (и) { addEventListener(и, поЖесту, {capture: true, passive: true}); }); } }
  function поЖесту() { жесты.forEach(function (и) { removeEventListener(и, поЖесту, {capture: true, passive: true}); }); ждём = false; все.forEach(function (с) { с.пуск(); }); }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) { все.forEach(function (с) { с.пуск(); }); } });
  addEventListener("pageshow", function () { все.forEach(function (с) { с.пуск(); }); });
  все.forEach(function (с) {
    var в = с.в;
    в.muted = true; в.setAttribute("playsinline", ""); в.setAttribute("webkit-playsinline", "");
    if (тихо || с.альфа) { в.pause(); в.removeAttribute("autoplay"); в.preload = "none"; if (тихо) { с.постер(true); } else { с.запасной(); } return; }
    if (в.hasAttribute("data-ролик-телефон") || в.hasAttribute("data-ролик-компьютер")) {
      с.выбрать(); if (узко.addEventListener) { узко.addEventListener("change", с.выбрать); } return;
    }
    if (узко.matches && в.getAttribute("data-телефон")) {   // старая пара: src элемента сильнее <source>
      в.setAttribute("poster", в.getAttribute("data-телефон-постер") || в.getAttribute("poster"));
      if (с.img && !с.img.hasAttribute("data-анимация-webp")) { с.img.src = в.getAttribute("poster"); }
      в.src = в.getAttribute("data-телефон"); в.load();
    }
    с.ждать();
  });
})();
