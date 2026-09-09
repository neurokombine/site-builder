// Живой таймер: тикает по data-дедлайн (ISO с +03:00 — московское время); дата прошла — блок исчезает. Date.now() здесь — осознанное исключение из правила «время везде московское»: это абсолютный момент, а дедлайн несёт +03:00, и разница между ними от пояса не зависит.
(function () {
  document.querySelectorAll("[data-дедлайн]").forEach(function (эл) {
    var конец = Date.parse(эл.getAttribute("data-дедлайн"));
    if (isNaN(конец)) { эл.hidden = true; return; }
    var поля = эл.querySelectorAll(".таймер__ячейка b");
    function тик() {
      var осталось = Math.max(0, конец - Date.now());
      if (осталось === 0) { эл.hidden = true; return; }
      var мин = Math.floor(осталось / 60000);
      var значения = [Math.floor(мин / 1440), Math.floor(мин / 60) % 24, мин % 60];
      поля.forEach(function (п, i) { п.textContent = String(значения[i]).padStart(2, "0"); });
    }
    тик(); setInterval(тик, 30000);
  });
})();
