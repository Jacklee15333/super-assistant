// line-icons.js — 把界面上的彩色表情图标（🎬 📁 🤖 👤 …）换成 Claude Code 风格的空心线条图标。
// 只改「界面」：聊天气泡、笔记正文、代码、输入框等 AI/用户写的内容一律不动。
// 静态页面和之后动态生成的内容都会自动处理（MutationObserver），不需要改各处的业务代码。
(function () {
  const P = {
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    video: '<rect x="2.5" y="6" width="13.5" height="12" rx="2.5"/><path d="m21.5 8.5-5.5 3.5 5.5 3.5z"/>',
    book: '<path d="M4 19.5V5a2 2 0 0 1 2-2h13v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M8 7h7"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    wrench: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
    hourglass: '<path d="M6 2h12M6 22h12M7 2v3.5a5 5 0 0 0 10 0V2M7 22v-3.5a5 5 0 0 1 10 0V22"/>',
    bot: '<rect x="4" y="8" width="16" height="12" rx="2.5"/><path d="M12 4v4M9 13.5h.01M15 13.5h.01M2 14h2M20 14h2"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8"/><path d="M18.2 14.2A6.5 6.5 0 0 1 21.5 20"/>',
    news: '<path d="M4 4h13v16H6a2 2 0 0 1-2-2z"/><path d="M17 8h3v10a2 2 0 0 1-2 2"/><path d="M8 8h5M8 12h5M8 16h5"/>',
    radar: '<circle cx="12" cy="12" r="2"/><path d="M16.2 7.8a6 6 0 0 1 0 8.5M7.8 16.2a6 6 0 0 1 0-8.5M19.1 4.9a10 10 0 0 1 0 14.2M4.9 19.1a10 10 0 0 1 0-14.2"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m20.5 20.5-4.8-4.8"/>',
    chat: '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.6 8.6 0 0 1-3.8-.9L3 21l1.9-5.2A8.4 8.4 0 0 1 3 11.5 8.5 8.5 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5z"/>',
    pencil: '<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    chart: '<path d="M4 20V4M4 20h16"/><path d="M8.5 16v-5M13 16V8M17.5 16v-3"/>',
    sparkle: '<path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
    camera: '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/>',
    brain: '<path d="M12 5.5a3 3 0 0 0-5.6-1.4A3 3 0 0 0 4 8.6a3.2 3.2 0 0 0 .6 5.4 3 3 0 0 0 3.2 4.6A3 3 0 0 0 12 19.5z"/><path d="M12 5.5a3 3 0 0 1 5.6-1.4A3 3 0 0 1 20 8.6a3.2 3.2 0 0 1-.6 5.4 3 3 0 0 1-3.2 4.6A3 3 0 0 1 12 19.5z"/>',
    db: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13"/><path d="M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    warn: '<path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.2h.01"/>',
    cross: '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
    star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 10h6M9 14h6"/>',
    repeat: '<path d="m17 2.5 3.5 3.5L17 9.5"/><path d="M3.5 11V10a4 4 0 0 1 4-4h13"/><path d="m7 21.5-3.5-3.5L7 14.5"/><path d="M20.5 13v1a4 4 0 0 1-4 4h-13"/>',
    sprout: '<path d="M7 20.5h10M12 20.5v-9"/><path d="M12 11.5c0-3.6-2.6-6.3-7.2-6.3 0 3.6 2.6 6.3 7.2 6.3z"/><path d="M12 13.5c0-3 2.1-5.3 6.2-5.3 0 3-2.1 5.3-6.2 5.3z"/>',
    network: '<circle cx="12" cy="5" r="2.2"/><circle cx="5" cy="18.5" r="2.2"/><circle cx="19" cy="18.5" r="2.2"/><path d="M12 7.2V12m0 0-5.4 4.8M12 12l5.4 4.8"/>',
    pet: '<path d="M4.5 9.5 6 3.5l4 3h4l4-3 1.5 6"/><path d="M4.5 9.5c0 6 3.4 10 7.5 10s7.5-4 7.5-10"/><path d="M9.5 12.5h.01M14.5 12.5h.01M11 15.5h2"/>',
    pulse: '<path d="M21.5 12h-4l-3 8.5-5-17-3 8.5h-4"/>',
    logout: '<path d="M9 20.5H5.5a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2H9"/><path d="m16 16.5 4.5-4.5L16 7.5M20.5 12H9"/>',
    file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
    download: '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
    upload: '<path d="M12 21V9M7 14l5-5 5 5M5 3h14"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    tv: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="m8 2 4 4 4-4"/>',
    bulb: '<path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/>',
    flask: '<path d="M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3"/><path d="M7 15h10"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    flame: '<path d="M12 22c4 0 7-2.8 7-7 0-4-3-6-4-9-1 2-2 3-4 3 0-2-1-4-2-5-1 3-4 6-4 11 0 4.2 3 7 7 7z"/>',
    rocket: '<path d="M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2"/><path d="M9 15 6.5 12.5C8 8 11 4 20 4c0 9-4 12-8.5 13.5z"/><circle cx="15" cy="9" r="1.5"/>',
    coins: '<circle cx="9" cy="9" r="6"/><path d="M15.5 9.5a6 6 0 1 1-6 6"/>',
    pin: '<path d="M12 22s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/>',
    tag: '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1.3"/>',
    lock: '<rect x="4.5" y="11" width="15" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    unlock: '<rect x="4.5" y="11" width="15" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.5-2"/>',
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    box: '<path d="m21 8-9-5-9 5v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    phone: '<rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M11 18h2"/>',
    monitor: '<rect x="2.5" y="4" width="19" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
    shield: '<path d="M12 3 4.5 6v6c0 4.6 3.2 7.9 7.5 9 4.3-1.1 7.5-4.4 7.5-9V6z"/>',
    home: '<path d="m3 11 9-7 9 7"/><path d="M5 10v10h14V10"/>',
    key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m11 12 9-9M17 6l3 3"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    speaker: '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7"/>',
    thumb: '<path d="M7 11v10H4V11zM7 11l4-8a2.5 2.5 0 0 1 2.5 2.5V9h5.5a2 2 0 0 1 2 2.3l-1.4 8A2 2 0 0 1 17.6 21H7"/>',
    cap: '<path d="m2 9 10-5 10 5-10 5z"/><path d="M6 11v5c3 2 9 2 12 0v-5"/>',
    map: '<path d="m9 4-6 2.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5z"/><path d="M9 4v13.5M15 6.5V20"/>',
    broom: '<path d="M14 4 20 10M5 21l4-9 6 6-9 4zM11 12l4-4"/>',
    seed: '<circle cx="12" cy="12" r="3"/>',
  };
  const MAP = {
    "📁": "folder", "📂": "folder", "🗂": "folder", "🗃": "box",
    "🎬": "video", "🎞": "video", "📹": "video", "🎥": "video", "▶️": "video",
    "📚": "book", "📖": "book", "📒": "book", "📓": "book", "📔": "book", "📕": "book", "📗": "book", "📘": "book", "📙": "book",
    "⚙": "gear", "🛠": "wrench", "🔧": "wrench", "🔨": "wrench", "⏳": "hourglass", "⌛": "hourglass",
    "🤖": "bot", "👤": "user", "👥": "users", "🎭": "users", "📰": "news", "🗞": "news", "📡": "radar",
    "🌐": "globe", "🌍": "globe", "🌏": "globe", "🌎": "globe", "🔍": "search", "🔎": "search",
    "💬": "chat", "🗨": "chat", "📝": "pencil", "✏": "pencil", "✍": "pencil", "🖊": "pencil", "🖋": "pencil",
    "📊": "chart", "📈": "chart", "📉": "chart", "🧩": "sparkle", "✨": "sparkle", "🆕": "sparkle", "🌟": "star", "⭐": "star",
    "🖼": "image", "🏞": "image", "📷": "camera", "📸": "camera", "🧠": "brain", "🗄": "db", "💾": "db",
    "✅": "check", "✔": "check", "☑": "check", "⚠": "warn", "❌": "cross", "✖": "cross", "🚫": "cross", "⛔": "cross",
    "🔔": "bell", "🎯": "target", "📋": "clipboard", "🔁": "repeat", "🔄": "repeat", "♻": "repeat",
    "🌱": "sprout", "🌌": "network", "🕸": "network", "🦊": "pet", "🐱": "pet", "🐾": "pet", "🦞": null,
    "💓": "pulse", "❤": "pulse", "💗": "pulse", "🔚": "logout", "📄": "file", "📃": "file", "📑": "file", "🧾": "file",
    "📥": "download", "⬇": "download", "📤": "upload", "⬆": "upload", "🗑": "trash", "🔗": "link",
    "🎵": "music", "🎶": "music", "📺": "tv", "💡": "bulb", "🧪": "flask", "🔬": "flask",
    "📅": "calendar", "📆": "calendar", "🗓": "calendar", "🕒": "clock", "⏰": "clock", "⏱": "clock", "🕐": "clock",
    "🔥": "flame", "🚀": "rocket", "💰": "coins", "💵": "coins", "🪙": "coins", "📌": "pin", "📍": "pin", "🏷": "tag",
    "🔒": "lock", "🔐": "lock", "🔓": "unlock", "⚡": "zap", "📦": "box", "📱": "phone", "💻": "monitor", "🖥": "monitor",
    "📧": "mail", "✉": "mail", "👀": "eye", "👁": "eye", "🛡": "shield", "🏠": "home", "🔑": "key",
    "🎤": "mic", "🎙": "mic", "🔊": "speaker", "🔈": "speaker", "👍": "thumb", "🎓": "cap", "🗺": "map", "🧭": "map", "🧹": "broom",
  };
  // 🦞 是软件的标志，保留彩色
  const keys = Object.keys(MAP).filter((k) => MAP[k]).sort((a, b) => b.length - a.length);
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const RE = new RegExp("(?:" + keys.map(esc).join("|") + ")\\uFE0F?", "gu");
  const SKIP = "textarea,input,select,option,pre,code,[contenteditable='true'],svg,script,style," +
               ".bubble,.msg,.markdown,.md,.md-body,.ddb-prev-md,.ddb-prev-pre,.video-result,#videoResult," +
               ".kg-canvas,#kgCanvas,.cx-noicon";

  function svgFor(key) {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor");
    s.setAttribute("stroke-width", "1.75"); s.setAttribute("stroke-linecap", "round"); s.setAttribute("stroke-linejoin", "round");
    s.setAttribute("class", "cx-ico"); s.setAttribute("aria-hidden", "true");
    s.innerHTML = P[key];
    return s;
  }

  function convertText(node) {
    const t = node.nodeValue;
    RE.lastIndex = 0;
    if (!t || !RE.test(t)) return;
    const par = node.parentElement;
    if (!par || par.closest(SKIP)) return;
    RE.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0, m;
    while ((m = RE.exec(t))) {
      if (m.index > last) frag.appendChild(document.createTextNode(t.slice(last, m.index)));
      const key = MAP[m[0]] || MAP[m[0].replace(/\uFE0F/g, "")];
      if (key) frag.appendChild(svgFor(key));
      last = m.index + m[0].length;
    }
    if (last < t.length) frag.appendChild(document.createTextNode(t.slice(last)));
    par.replaceChild(frag, node);
  }

  function cleanOptions(root) {
    (root.querySelectorAll ? root.querySelectorAll("option") : []).forEach((o) => {
      RE.lastIndex = 0;
      if (RE.test(o.textContent)) { RE.lastIndex = 0; o.textContent = o.textContent.replace(RE, "").replace(/^\s+/, ""); }
    });
  }

  function iconize(root) {
    if (!root) return;
    if (root.nodeType === 3) { convertText(root); return; }
    if (root.nodeType !== 1 || root.closest && root.closest(SKIP)) {
      if (root.nodeType === 1 && (root.tagName === "SELECT" || root.tagName === "OPTION")) cleanOptions(root.tagName === "OPTION" ? root.parentElement || root : root);
      return;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(convertText);
    cleanOptions(root);
  }

  let pending = new Set(), scheduled = false;
  function flush() {
    scheduled = false;
    const list = [...pending]; pending = new Set();
    list.forEach((n) => { if (n.isConnected) iconize(n); });
  }
  const mo = new MutationObserver((muts) => {
    for (const m of muts) {
      if (m.type === "characterData") pending.add(m.target);
      else m.addedNodes.forEach((n) => pending.add(n));
    }
    if (!scheduled && pending.size) { scheduled = true; requestAnimationFrame(flush); }
  });
  iconize(document.body);
  mo.observe(document.body, { childList: true, subtree: true, characterData: true });
  window.cxIconize = iconize;
})();
