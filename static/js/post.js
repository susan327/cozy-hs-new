// static/post.js
// サーバー側（Jinja）で一覧を描画する前提。
// ここでは画像プレビューだけ担当する。

function previewImage() {
  const fileInput = document.getElementById("image");
  const preview = document.getElementById("preview");
  if (!fileInput || !preview) return;

  // いったん消す
  preview.innerHTML = "";

  const file = fileInput.files && fileInput.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    const img = document.createElement("img");
    img.src = e.target.result;
    img.style.maxWidth = "100%";
    img.style.height = "auto";
    img.style.borderRadius = "8px";
    img.style.boxShadow = "0 2px 6px rgba(0,0,0,0.1)";
    preview.appendChild(img);
  };
  reader.readAsDataURL(file);
}

// ★ 重要：クライアントで一覧をfetchして描画する処理は削除！
// fetch("/api/news") ... のようなコードは一切入れない。
