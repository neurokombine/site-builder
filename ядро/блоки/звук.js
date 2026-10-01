// Живая сцена: браузеры запускают видео только без звука — голос по одному нажатию кнопки .звук. По нажатию: звук,
// без петли, с начала; на ended и при уходе со вкладки — снова тихая петля. Ролик обложки играет и при reduced-motion (спокойная петля, решение после проверки на живых телефонах), звук — по нажатию как всегда.
(function () {
  var видео = document.querySelector(".картинка--видео-с-голосом video"), кнопка = document.querySelector(".звук");
  if (!видео || !кнопка) { return; }
  var фигура = видео.closest(".картинка"), блок = кнопка.parentNode, подпись = кнопка.querySelector(".звук__подпись");
  var вкл = кнопка.querySelector(".звук__вкл"), выкл = кнопка.querySelector(".звук__выкл");
  function состояние(звук) {
    кнопка.setAttribute("aria-pressed", звук ? "true" : "false");
    кнопка.setAttribute("aria-label", звук ? "Выключить звук" : "Включить звук");
    подпись.textContent = звук ? "Выключить звук" : "Включить звук";
    if (вкл && выкл) { вкл.toggleAttribute("hidden", !звук); выкл.toggleAttribute("hidden", звук); }   // svg <path>: свойства hidden нет
    блок.setAttribute("data-звук", звук ? "вкл" : "выкл");
  }
  function тихо() { видео.muted = true; видео.loop = true; состояние(false); var п = видео.play(); if (п && п.catch) { п.catch(function () {}); } }
  кнопка.addEventListener("click", function () {
    if (!видео.muted) { тихо(); return; }
    фигура.classList.remove("картинка--постер");   // автозапуск был заблокирован — обложка.js показала постер; нажатие всё равно запускает
    видео.muted = false; видео.loop = false; видео.currentTime = 0; состояние(true);
    var п = видео.play(); if (п && п.catch) { п.catch(тихо); }
  });
  видео.addEventListener("ended", function () { if (!видео.muted) { тихо(); } });
  document.addEventListener("visibilitychange", function () { if (document.hidden && !видео.muted) { тихо(); } });
})();
