// static/news.js
document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("news-list");

  // 日本時間表示に変換
  function formatTokyo(iso) {
    if (!iso) return "";
    let fixed = String(iso).replace(/(\.\d{3})\d+/, "$1"); // ミリ秒丸め
    if (!/[zZ]|[+\-]\d{2}:\d{2}$/.test(fixed)) fixed += "Z"; // TZなければZ付与
    const d = new Date(fixed);
    return new Intl.DateTimeFormat("ja-JP", {
      timeZone: "Asia/Tokyo",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }).format(d);
  }

  fetch("/api/news")
    .then(res => res.json())
    .then(posts => {
      // 新しい順にソート（timestamp優先、同一ならid降順）
      posts.sort((a, b) => {
        const ta = new Date(a.timestamp || 0).getTime();
        const tb = new Date(b.timestamp || 0).getTime();
        if (tb !== ta) return tb - ta;
        return (b.id || 0) - (a.id || 0);
      });

      // 最新3件だけ表示
      posts.slice(0, 3).forEach(post => {
        const div = document.createElement("div");
        div.className = "card";

        const title = document.createElement("div");
        title.className = "title";
        title.textContent = post.title || "(タイトルなし)";

        const date = document.createElement("div");
        date.className = "date";
        date.textContent = formatTokyo(post.timestamp);

        const body = document.createElement("div");
        body.className = "body";
        body.innerHTML = (post.body || "").replace(/\n/g, "<br>");

        div.appendChild(title);
        div.appendChild(date);
        div.appendChild(body);

        if (post.image && !post.image.startsWith("data:image")) {
          const img = document.createElement("img");
          img.src = post.image;
          img.alt = "投稿画像";
          img.style.maxWidth = "300px";
          img.style.width = "100%";
          img.style.height = "auto";
          img.style.borderRadius = "8px";
          img.style.boxShadow = "0 2px 6px rgba(0,0,0,0.1)";
          img.style.marginTop = "0.5em";
          div.appendChild(img);
        }

        container.appendChild(div);
      });
    });
});
