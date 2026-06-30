/* pet-characters.js — 桌宠「角色库」（数据驱动，方便以后加新角色）
 *
 * 设计目标：
 *   1. 每个角色 = 一份配置 + 一个 SVG 生成函数。加新角色只要往 PET_CHARACTERS 里再 push 一项。
 *   2. SVG 是矢量的，放大不糊，颜色用变量，方便换肤。
 *   3. 角色支持几种姿态(pose)：idle(站着微微呼吸)、walk(走动，腿/尾巴动)、sleep(睡觉)、
 *      happy(开心/被点)。pose 由 pet.js 的状态机驱动，这里只负责「长什么样」。
 *   4. 也支持「自定义角色」：type:"image" 用一张用户自己的图片当桌宠（emoji 或图片 URL）。
 *
 * 用法：
 *   const c = getCharacter("fox");
 *   el.innerHTML = c.svg({ pose:"walk", facing:1, frame: 12, blink:false });
 *   // facing: 1=朝右, -1=朝左；frame: 递增的帧计数(用于动画相位)；blink:是否眨眼这一帧
 */

(function (global) {
  "use strict";

  // 小工具：把 0~1 的相位转成上下浮动像素（呼吸/走路的弹跳感）
  function bob(frame, speed, amp) {
    return Math.sin((frame * speed)) * amp;
  }

  // ───────────────────────── 角色：小狐狸 fox（首发主角）─────────────────────────
  // 月光银白 + 暖橘耳尖，灵动大耳朵会抖，毛茸茸尾巴会摇。像素感但用矢量画。
  function foxSVG(s) {
    var pose = s.pose || "idle";
    var face = (s.facing === -1) ? -1 : 1;
    var f = s.frame || 0;
    var blink = !!s.blink;

    // 颜色（换肤就改这里）
    var FUR = "#f2f4f8";       // 主体银白
    var FUR_SHADE = "#d9deea";  // 暗部
    var ACCENT = "#ff8a4c";     // 暖橘（耳尖/爪/尾尖）
    var ACCENT_DK = "#e8702f";
    var INNER = "#ffd9c2";      // 耳朵内侧/肚皮
    var EYE = "#2b2f3a";
    var NOSE = "#34384a";

    // 走路时身体上下弹 + 腿摆动；idle 时极轻微呼吸；sleep 趴下
    var walk = (pose === "walk");
    var sleep = (pose === "sleep");
    var happy = (pose === "happy");

    var bodyY = sleep ? 16 : (walk ? bob(f, 0.5, 2.2) : bob(f, 0.18, 1.0));
    var earTwitch = walk ? bob(f, 0.6, 3) : bob(f, 0.12, 1.4);
    var tailWag = walk ? bob(f, 0.55, 10) : bob(f, 0.2, 5) + (happy ? bob(f, 0.9, 8) : 0);
    // 两条前腿/后腿相位相反，制造交替迈步
    var legA = walk ? bob(f, 0.5, 5) : 0;
    var legB = walk ? bob(f + 3.14, 0.5, 5) : 0;

    var eyeRY = (blink && !sleep) ? 0.6 : (sleep ? 0.5 : 3.0);
    var mouthHappy = happy || sleep;

    // 朝向：整体水平翻转
    var flip = (face === -1)
      ? 'transform="translate(64,0) scale(-1,1)"'
      : '';

    // sleep 时画几个 Z
    var zzz = sleep
      ? '<g opacity="0.8" fill="#9aa3b8" font-family="monospace" font-weight="700">' +
        '<text x="44" y="20" font-size="9">z</text>' +
        '<text x="50" y="13" font-size="7">z</text>' +
        '</g>'
      : "";

    return '' +
    '<svg viewBox="0 0 64 64" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" shape-rendering="geometricPrecision">' +
      '<g ' + flip + '>' +
        // 影子
        '<ellipse cx="32" cy="' + (sleep ? 56 : 58) + '" rx="' + (sleep ? 20 : 14) + '" ry="3.2" fill="#000" opacity="0.14"/>' +
        '<g transform="translate(0,' + bodyY.toFixed(2) + ')">' +
          // 尾巴（在身体后面，会摇）
          '<g transform="rotate(' + tailWag.toFixed(2) + ' 16 42)">' +
            '<path d="M18 42 C6 40 2 30 6 24 C8 33 14 36 20 38 Z" fill="' + FUR + '"/>' +
            '<path d="M8 26 C5 30 6 36 12 39 C9 35 9 31 11 28 Z" fill="' + ACCENT + '" opacity="0.95"/>' +
          '</g>' +

          // 后腿
          '<rect x="34" y="' + (44 + legB).toFixed(2) + '" width="6" height="10" rx="3" fill="' + FUR_SHADE + '"/>' +
          '<rect x="34" y="' + (52 + Math.max(0, legB)).toFixed(2) + '" width="6" height="3" rx="1.5" fill="' + ACCENT + '"/>' +

          // 身体
          (sleep
            ? '<ellipse cx="32" cy="46" rx="20" ry="12" fill="' + FUR + '"/>' +
              '<ellipse cx="32" cy="49" rx="14" ry="7" fill="' + INNER + '" opacity="0.6"/>'
            : '<path d="M20 34 C20 26 44 26 44 34 L44 46 C44 52 20 52 20 46 Z" fill="' + FUR + '"/>' +
              '<path d="M24 40 C24 36 40 36 40 40 L40 46 C40 50 24 50 24 46 Z" fill="' + INNER + '" opacity="0.7"/>') +

          // 前腿
          (sleep ? '' :
            '<rect x="22" y="' + (44 + legA).toFixed(2) + '" width="6" height="10" rx="3" fill="' + FUR + '"/>' +
            '<rect x="22" y="' + (52 + Math.max(0, legA)).toFixed(2) + '" width="6" height="3" rx="1.5" fill="' + ACCENT + '"/>') +

          // 头
          '<g transform="translate(0,' + (sleep ? 2 : 0) + ')">' +
            // 耳朵（会抖）
            '<g transform="translate(' + earTwitch.toFixed(2) + ',0)">' +
              '<path d="M21 24 L18 10 L29 19 Z" fill="' + FUR + '"/>' +
              '<path d="M22 22 L20.5 13 L26 18 Z" fill="' + INNER + '"/>' +
              '<path d="M19 11 L18 10 L21 13 Z" fill="' + ACCENT + '"/>' +
            '</g>' +
            '<g transform="translate(' + (-earTwitch).toFixed(2) + ',0)">' +
              '<path d="M43 24 L46 10 L35 19 Z" fill="' + FUR + '"/>' +
              '<path d="M42 22 L43.5 13 L38 18 Z" fill="' + INNER + '"/>' +
              '<path d="M45 11 L46 10 L43 13 Z" fill="' + ACCENT + '"/>' +
            '</g>' +
            // 脸
            '<path d="M20 26 C20 18 44 18 44 26 C44 34 38 38 32 38 C26 38 20 34 20 26 Z" fill="' + FUR + '"/>' +
            // 白色口鼻区
            '<path d="M27 30 C27 34 37 34 37 30 C37 36 32 39 32 39 C32 39 27 36 27 30 Z" fill="#ffffff"/>' +
            // 眼睛
            '<ellipse cx="27" cy="27" rx="2.2" ry="' + eyeRY + '" fill="' + EYE + '"/>' +
            '<ellipse cx="37" cy="27" rx="2.2" ry="' + eyeRY + '" fill="' + EYE + '"/>' +
            (sleep || blink ? '' :
              '<circle cx="27.7" cy="26" r="0.7" fill="#fff"/><circle cx="37.7" cy="26" r="0.7" fill="#fff"/>') +
            // 鼻子
            '<path d="M30.5 31 L33.5 31 L32 33 Z" fill="' + NOSE + '"/>' +
            // 嘴
            (mouthHappy
              ? '<path d="M30 34 Q32 37 34 34" stroke="' + NOSE + '" stroke-width="1" fill="none" stroke-linecap="round"/>'
              : '<path d="M32 33 L32 35 M32 35 Q30 36 29 35 M32 35 Q34 36 35 35" stroke="' + NOSE + '" stroke-width="0.9" fill="none" stroke-linecap="round"/>') +
            // 腮红（happy 时出现）
            (happy
              ? '<circle cx="24" cy="31" r="2" fill="' + ACCENT + '" opacity="0.35"/>' +
                '<circle cx="40" cy="31" r="2" fill="' + ACCENT + '" opacity="0.35"/>'
              : '') +
          '</g>' +
        '</g>' +
      '</g>' +
      zzz +
    '</svg>';
  }

  // ───────────────────────── 角色：小螃蟹 Clawd（跟软件图标呼应）─────────────────
  function crabSVG(s) {
    var pose = s.pose || "idle";
    var face = (s.facing === -1) ? -1 : 1;
    var f = s.frame || 0;
    var blink = !!s.blink;
    var SHELL = "#e8623a", SHELL_DK = "#c84a27", BELLY = "#ffb59c", EYE = "#1d2430";
    var walk = (pose === "walk"), sleep = (pose === "sleep"), happy = (pose === "happy");
    var bodyY = sleep ? 12 : (walk ? bob(f, 0.6, 1.8) : bob(f, 0.2, 0.9));
    var claw = walk ? bob(f, 0.7, 6) : (happy ? bob(f, 1.1, 9) : bob(f, 0.25, 3));
    var legA = walk ? bob(f, 0.6, 4) : 0;
    var legB = walk ? bob(f + 3.14, 0.6, 4) : 0;
    var eyeRY = (blink && !sleep) ? 0.5 : 3.0;
    var flip = (face === -1) ? 'transform="translate(64,0) scale(-1,1)"' : '';
    var zzz = sleep ? '<text x="46" y="20" font-size="9" fill="#9aa3b8" font-family="monospace" font-weight="700">z</text>' : "";
    return '' +
    '<svg viewBox="0 0 64 64" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">' +
      '<g ' + flip + '>' +
        '<ellipse cx="32" cy="56" rx="18" ry="3" fill="#000" opacity="0.14"/>' +
        '<g transform="translate(0,' + bodyY.toFixed(2) + ')">' +
          // 腿（左右各3）
          (function () { var o = ""; for (var i = 0; i < 3; i++) {
            var dy = (i % 2 ? legA : legB);
            o += '<path d="M20 ' + (40 + i * 4) + ' L8 ' + (44 + i * 4 + dy).toFixed(2) + '" stroke="' + SHELL_DK + '" stroke-width="2.4" stroke-linecap="round"/>';
            o += '<path d="M44 ' + (40 + i * 4) + ' L56 ' + (44 + i * 4 + dy).toFixed(2) + '" stroke="' + SHELL_DK + '" stroke-width="2.4" stroke-linecap="round"/>';
          } return o; })() +
          // 大钳子
          '<g transform="rotate(' + (-claw).toFixed(2) + ' 16 38)">' +
            '<path d="M20 36 L10 34" stroke="' + SHELL_DK + '" stroke-width="3" stroke-linecap="round"/>' +
            '<path d="M10 30 C4 30 4 38 10 38 C8 35 8 33 10 34 Z" fill="' + SHELL + '"/>' +
          '</g>' +
          '<g transform="rotate(' + claw.toFixed(2) + ' 48 38)">' +
            '<path d="M44 36 L54 34" stroke="' + SHELL_DK + '" stroke-width="3" stroke-linecap="round"/>' +
            '<path d="M54 30 C60 30 60 38 54 38 C56 35 56 33 54 34 Z" fill="' + SHELL + '"/>' +
          '</g>' +
          // 身体（壳）
          '<path d="M16 36 C16 26 48 26 48 36 C48 44 40 48 32 48 C24 48 16 44 16 36 Z" fill="' + SHELL + '"/>' +
          '<path d="M22 38 C22 34 42 34 42 38 C42 43 36 45 32 45 C28 45 22 43 22 38 Z" fill="' + BELLY + '" opacity="0.55"/>' +
          // 眼柄 + 眼睛
          '<rect x="26" y="22" width="2" height="8" rx="1" fill="' + SHELL_DK + '"/>' +
          '<rect x="36" y="22" width="2" height="8" rx="1" fill="' + SHELL_DK + '"/>' +
          '<circle cx="27" cy="21" r="3.4" fill="#fff"/><ellipse cx="27" cy="21" rx="1.6" ry="' + eyeRY + '" fill="' + EYE + '"/>' +
          '<circle cx="37" cy="21" r="3.4" fill="#fff"/><ellipse cx="37" cy="21" rx="1.6" ry="' + eyeRY + '" fill="' + EYE + '"/>' +
          (happy ? '<path d="M28 40 Q32 44 36 40" stroke="' + SHELL_DK + '" stroke-width="1.2" fill="none" stroke-linecap="round"/>'
                 : '<path d="M29 41 Q32 43 35 41" stroke="' + SHELL_DK + '" stroke-width="1" fill="none" stroke-linecap="round"/>') +
        '</g>' +
      '</g>' + zzz +
    '</svg>';
  }

  // ───────────────────────── 角色：小猫咪 cat ─────────────────────────
  function catSVG(s) {
    var pose = s.pose || "idle";
    var face = (s.facing === -1) ? -1 : 1;
    var f = s.frame || 0;
    var blink = !!s.blink;
    var FUR = "#9aa7b4", FUR_DK = "#7c8997", INNER = "#ffd3d8", EYE = "#2b6f4e", NOSE = "#d56a7a";
    var walk = (pose === "walk"), sleep = (pose === "sleep"), happy = (pose === "happy");
    var bodyY = sleep ? 16 : (walk ? bob(f, 0.5, 2) : bob(f, 0.18, 0.9));
    var tail = walk ? bob(f, 0.5, 12) : bob(f, 0.22, 7);
    var ear = walk ? bob(f, 0.6, 2) : bob(f, 0.12, 1);
    var legA = walk ? bob(f, 0.5, 5) : 0, legB = walk ? bob(f + 3.14, 0.5, 5) : 0;
    var eyeRY = (blink && !sleep) ? 0.5 : 3.2;
    var flip = (face === -1) ? 'transform="translate(64,0) scale(-1,1)"' : '';
    var zzz = sleep ? '<text x="46" y="18" font-size="9" fill="#9aa3b8" font-family="monospace" font-weight="700">z</text>' : "";
    return '' +
    '<svg viewBox="0 0 64 64" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">' +
      '<g ' + flip + '>' +
        '<ellipse cx="32" cy="' + (sleep ? 56 : 58) + '" rx="' + (sleep ? 18 : 13) + '" ry="3" fill="#000" opacity="0.14"/>' +
        '<g transform="translate(0,' + bodyY.toFixed(2) + ')">' +
          '<g transform="rotate(' + tail.toFixed(2) + ' 18 44)">' +
            '<path d="M20 44 C8 44 6 32 12 28" stroke="' + FUR + '" stroke-width="5" fill="none" stroke-linecap="round"/>' +
            '<circle cx="12" cy="28" r="3" fill="' + FUR_DK + '"/>' +
          '</g>' +
          '<rect x="34" y="' + (45 + legB).toFixed(2) + '" width="6" height="9" rx="3" fill="' + FUR_DK + '"/>' +
          (sleep
            ? '<ellipse cx="32" cy="46" rx="19" ry="11" fill="' + FUR + '"/>'
            : '<path d="M21 35 C21 27 43 27 43 35 L43 46 C43 51 21 51 21 46 Z" fill="' + FUR + '"/>') +
          (sleep ? '' : '<rect x="22" y="' + (45 + legA).toFixed(2) + '" width="6" height="9" rx="3" fill="' + FUR + '"/>') +
          '<g transform="translate(0,' + (sleep ? 2 : 0) + ')">' +
            '<g transform="translate(' + ear.toFixed(2) + ',0)"><path d="M22 24 L20 12 L30 20 Z" fill="' + FUR + '"/><path d="M23 22 L22 15 L27 19 Z" fill="' + INNER + '"/></g>' +
            '<g transform="translate(' + (-ear).toFixed(2) + ',0)"><path d="M42 24 L44 12 L34 20 Z" fill="' + FUR + '"/><path d="M41 22 L42 15 L37 19 Z" fill="' + INNER + '"/></g>' +
            '<ellipse cx="32" cy="28" rx="12" ry="10" fill="' + FUR + '"/>' +
            '<ellipse cx="27" cy="27" rx="2.4" ry="' + eyeRY + '" fill="' + EYE + '"/>' +
            '<ellipse cx="37" cy="27" rx="2.4" ry="' + eyeRY + '" fill="' + EYE + '"/>' +
            (sleep || blink ? '' : '<circle cx="27.8" cy="25.8" r="0.7" fill="#fff"/><circle cx="37.8" cy="25.8" r="0.7" fill="#fff"/>') +
            '<path d="M30.5 30 L33.5 30 L32 32 Z" fill="' + NOSE + '"/>' +
            (happy ? '<path d="M30 33 Q32 35 34 33" stroke="' + FUR_DK + '" stroke-width="1" fill="none" stroke-linecap="round"/>'
                   : '<path d="M32 32 L32 33 M32 33 Q30.5 34.5 29.5 33.5 M32 33 Q33.5 34.5 34.5 33.5" stroke="' + FUR_DK + '" stroke-width="0.9" fill="none" stroke-linecap="round"/>') +
            // 胡须
            '<g stroke="#cfd6dd" stroke-width="0.7" stroke-linecap="round">' +
              '<path d="M24 30 L16 29"/><path d="M24 32 L16 33"/><path d="M40 30 L48 29"/><path d="M40 32 L48 33"/></g>' +
            (happy ? '<circle cx="24" cy="31" r="2" fill="' + NOSE + '" opacity="0.3"/><circle cx="40" cy="31" r="2" fill="' + NOSE + '" opacity="0.3"/>' : '') +
          '</g>' +
        '</g>' +
      '</g>' + zzz +
    '</svg>';
  }

  // ───────────────────────── 角色：像素小机器人 robot ─────────────────────────
  function robotSVG(s) {
    var pose = s.pose || "idle";
    var face = (s.facing === -1) ? -1 : 1;
    var f = s.frame || 0;
    var blink = !!s.blink;
    var BODY = "#7b8aa0", BODY_DK = "#5d6b80", GLOW = "#4cc9ff", METAL = "#aeb9c9", EYE = "#0e1726";
    var walk = (pose === "walk"), sleep = (pose === "sleep"), happy = (pose === "happy");
    var bodyY = sleep ? 8 : (walk ? bob(f, 0.5, 1.6) : bob(f, 0.16, 0.7));
    var antenna = bob(f, 0.4, 2) + (happy ? bob(f, 1.2, 3) : 0);
    var legA = walk ? bob(f, 0.5, 4) : 0, legB = walk ? bob(f + 3.14, 0.5, 4) : 0;
    var eyeGlow = sleep ? 0.25 : (blink ? 0.3 : 1);
    var flip = (face === -1) ? 'transform="translate(64,0) scale(-1,1)"' : '';
    var zzz = sleep ? '<text x="46" y="16" font-size="9" fill="#9aa3b8" font-family="monospace" font-weight="700">z</text>' : "";
    return '' +
    '<svg viewBox="0 0 64 64" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">' +
      '<g ' + flip + '>' +
        '<ellipse cx="32" cy="58" rx="13" ry="3" fill="#000" opacity="0.16"/>' +
        '<g transform="translate(0,' + bodyY.toFixed(2) + ')">' +
          // 天线
          '<line x1="32" y1="18" x2="' + (32 + antenna).toFixed(2) + '" y2="9" stroke="' + METAL + '" stroke-width="1.6"/>' +
          '<circle cx="' + (32 + antenna).toFixed(2) + '" cy="8" r="2.4" fill="' + GLOW + '"/>' +
          // 腿
          '<rect x="23" y="' + (48 + legA).toFixed(2) + '" width="6" height="8" rx="2" fill="' + BODY_DK + '"/>' +
          '<rect x="35" y="' + (48 + legB).toFixed(2) + '" width="6" height="8" rx="2" fill="' + BODY_DK + '"/>' +
          // 身体
          '<rect x="20" y="32" width="24" height="20" rx="6" fill="' + BODY + '"/>' +
          '<rect x="24" y="36" width="16" height="9" rx="3" fill="' + BODY_DK + '"/>' +
          '<circle cx="28" cy="40.5" r="1.6" fill="' + GLOW + '" opacity="' + (happy ? 1 : 0.7) + '"/>' +
          '<rect x="32" y="39.5" width="6" height="2" rx="1" fill="' + GLOW + '" opacity="0.7"/>' +
          // 头
          '<rect x="22" y="18" width="20" height="16" rx="5" fill="' + METAL + '"/>' +
          '<rect x="25" y="22" width="14" height="8" rx="3" fill="' + EYE + '"/>' +
          '<circle cx="29" cy="26" r="2.2" fill="' + GLOW + '" opacity="' + eyeGlow + '"/>' +
          '<circle cx="35" cy="26" r="2.2" fill="' + GLOW + '" opacity="' + eyeGlow + '"/>' +
          (happy ? '<path d="M29 31 Q32 33 35 31" stroke="' + GLOW + '" stroke-width="1" fill="none" stroke-linecap="round" opacity="0.8"/>' : '') +
          // 手臂
          '<rect x="16" y="34" width="4" height="10" rx="2" fill="' + BODY_DK + '"/>' +
          '<rect x="44" y="34" width="4" height="10" rx="2" fill="' + BODY_DK + '"/>' +
        '</g>' +
      '</g>' + zzz +
    '</svg>';
  }

  // ───────────────────────── 自定义角色：用一张图/emoji 当桌宠 ─────────────────────────
  // cfg.image 可以是 emoji 字符串(如 "🐥") 或 data:/file: 图片 URL
  function imageSVG(cfg) {
    return function (s) {
      var f = s.frame || 0;
      var pose = s.pose || "idle";
      var bobY = (pose === "walk") ? bob(f, 0.5, 2.4) : bob(f, 0.2, 1.2);
      var img = cfg.image || "🐾";
      var isEmoji = !/^(data:|file:|https?:|\.|\/)/i.test(img) && img.length <= 4;
      var inner = isEmoji
        ? '<text x="32" y="44" font-size="40" text-anchor="middle">' + img + '</text>'
        : '<image href="' + img + '" x="8" y="8" width="48" height="48" preserveAspectRatio="xMidYMid meet"/>';
      return '<svg viewBox="0 0 64 64" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">' +
        '<ellipse cx="32" cy="58" rx="13" ry="3" fill="#000" opacity="0.14"/>' +
        '<g transform="translate(0,' + bobY.toFixed(2) + ')">' + inner + '</g></svg>';
    };
  }

  // ───────────────────────── 角色总表 ─────────────────────────
  // 加新角色：往这里再加一项 { id, name, emoji, accent, svg }
  var PET_CHARACTERS = [
    { id: "fox",   name: "小狐狸", emoji: "🦊", accent: "#ff8a4c", svg: foxSVG,
      hello: ["嗅到新东西啦~", "我在呢！", "今天也一起加油？"] },
    { id: "crab",  name: "小螃蟹", emoji: "🦞", accent: "#e8623a", svg: crabSVG,
      hello: ["横着也能陪你！", "钳一下问题~", "我是 Clawd！"] },
    { id: "cat",   name: "小猫咪", emoji: "🐱", accent: "#9aa7b4", svg: catSVG,
      hello: ["喵~ 需要帮忙吗", "蹭一蹭", "在摸鱼…啊不，在待命"] },
    { id: "robot", name: "小机器人", emoji: "🤖", accent: "#4cc9ff", svg: robotSVG,
      hello: ["系统就绪。", "指令请讲~", "嘀——已上线"] },
  ];

  var _byId = {};
  PET_CHARACTERS.forEach(function (c) { _byId[c.id] = c; });

  function getCharacter(id, customCfg) {
    if (id === "custom" && customCfg) {
      return {
        id: "custom",
        name: customCfg.name || "我的桌宠",
        emoji: (customCfg.image && customCfg.image.length <= 4) ? customCfg.image : "⭐",
        accent: customCfg.accent || "#7B68EE",
        svg: imageSVG(customCfg),
        hello: customCfg.hello || ["你好呀~", "我在这里！"]
      };
    }
    return _byId[id] || _byId["fox"];
  }

  function listCharacters() {
    return PET_CHARACTERS.map(function (c) {
      return { id: c.id, name: c.name, emoji: c.emoji, accent: c.accent };
    });
  }

  var api = { getCharacter: getCharacter, listCharacters: listCharacters, PET_CHARACTERS: PET_CHARACTERS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.PetCharacters = api;
})(typeof window !== "undefined" ? window : this);
