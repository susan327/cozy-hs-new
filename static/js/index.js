// Tabletop.js を使ってスプレッドシートを読み込み
window.addEventListener('DOMContentLoaded', function () {
  Tabletop.init({
    key: 'https://docs.google.com/spreadsheets/d/19OEtVwfJ3Rh__GRSYE8JOF8_X-I3R0DfyzEDQTvUjnc/pubhtml',
    callback: function (data) {
      const newsList = document.getElementById('news-list');
      data.slice(0, 5).forEach(item => {
        const li = document.createElement('li');
        li.textContent = `【${item['日付']}】${item['内容']}`;
        newsList.appendChild(li);
      });
    },
    simpleSheet: true
  });
});
