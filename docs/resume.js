/* Resume tailoring. Runs in the browser, nothing is sent anywhere.
   It never writes new claims: it only picks, orders and highlights what is already in the master resume. */
(function (root) {
  var STOP = new Set(("the and for with that this you your our are will from have has not but all can their they who what out more about into over than also been were was may per via etc such other any " +
    "work team role job company include including able ability experience years year strong skills new use using across within help support provide need needs must should would one two " +
    "candidate candidates position responsibilities requirements qualifications preferred required plus benefits equal opportunity employer apply join looking seeking ideal we're you'll " +
    "working based related ensure manage managing within while through between both well like make high good great best part full time remote hybrid location salary pay range").split(" "));

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function wordsOf(t) {
    var m = String(t || "").toLowerCase().match(/[a-z][a-z0-9+#]{2,}/g) || [];
    return m.filter(function (w) { return !STOP.has(w); });
  }
  function freq(list) {
    var f = {};
    list.forEach(function (w) { f[w] = (f[w] || 0) + 1; });
    return f;
  }
  function trim(s) { return s.trim(); }

  /* Master resume format:
       Full Name
       email | phone | City, ST | linkedin
       # SUMMARY
       text
       # SKILLS
       skill one, skill two
       # EXPERIENCE
       Job Title | Company | City, ST | 2019 to 2024
       - bullet
       # EDUCATION
       Degree, School
       # CERTIFICATIONS
       Certification, year                                                        */
  function parseResume(text) {
    var r = { name: "", contact: "", headline: "", summary: "", skills: [], exp: [], edu: [], certs: [], other: [] };
    var sec = null, head = [];
    String(text || "").replace(/\r/g, "").split("\n").forEach(function (raw) {
      var l = raw.trim();
      if (!l) return;
      var m = l.match(/^#+\s*(.+)$/);
      if (m) { sec = m[1].toLowerCase(); return; }
      if (!sec) { head.push(l); return; }
      var bullet = /^[-•*]\s*/;
      if (sec.indexOf("summary") === 0) { r.summary += (r.summary ? " " : "") + l; return; }
      if (sec.indexOf("skill") === 0) { l.split(/[,;]/).forEach(function (s) { s = s.trim(); if (s) r.skills.push(s); }); return; }
      if (sec.indexOf("experience") === 0) {
        if (bullet.test(l)) {
          if (!r.exp.length) r.exp.push({ head: [], bullets: [] });
          r.exp[r.exp.length - 1].bullets.push(l.replace(bullet, ""));
        } else {
          r.exp.push({ head: l.split("|").map(trim), bullets: [] });
        }
        return;
      }
      if (sec.indexOf("education") === 0) { r.edu.push(l.replace(bullet, "")); return; }
      if (sec.indexOf("cert") === 0) { r.certs.push(l.replace(bullet, "")); return; }
      r.other.push(l.replace(bullet, ""));
    });
    r.name = head[0] || "";
    r.contact = head.slice(1).join(" | ");
    return r;
  }

  function resumeWords(res) {
    var all = [res.name, res.summary, res.skills.join(" "), res.edu.join(" "), res.certs.join(" ")];
    res.exp.forEach(function (e) { all.push(e.head.join(" ")); all.push(e.bullets.join(" ")); });
    return all.join(" ").toLowerCase();
  }

  function tailor(res, job, cfg) {
    var text = (job.title || "") + " " + (job.text || "");
    var lt = text.toLowerCase();
    var jw = freq(wordsOf(text));
    var top = Object.keys(jw).sort(function (a, b) { return jw[b] - jw[a] || (a < b ? -1 : 1); }).slice(0, 60);
    var topSet = {};
    top.forEach(function (w) { topSet[w] = 1; });

    var phrases = [];
    Object.keys((cfg && cfg.positive_terms) || {}).forEach(function (p) { if (lt.indexOf(p) >= 0) phrases.push(p); });
    var roles = (cfg && cfg.roles) || {};
    Object.keys(roles).forEach(function (g) {
      roles[g].forEach(function (p) {
        p = p.toLowerCase();
        if (p.indexOf(" ") >= 0 && lt.indexOf(p) >= 0) phrases.push(p);
      });
    });

    function scoreText(t) {
      var lw = t.toLowerCase(), s = 0, seen = {};
      wordsOf(t).forEach(function (w) { if (topSet[w] && !seen[w]) { seen[w] = 1; s += 1; } });
      phrases.forEach(function (p) { if (lw.indexOf(p) >= 0) s += 3; });
      return s;
    }

    var out = JSON.parse(JSON.stringify(res));
    out.headline = (job.title || "").replace(/\s*\([^)]*\)\s*/g, " ").trim();
    out.exp.forEach(function (e, i) {
      var keep = i < 2 ? 6 : 4;
      var ranked = e.bullets.map(function (b, k) { return { b: b, k: k, s: scoreText(b) }; });
      ranked.sort(function (a, b) { return b.s - a.s || a.k - b.k; });
      e.bullets = ranked.slice(0, keep).map(function (x) { return x.b; });
    });
    var sk = res.skills.map(function (s, k) { return { s: s, k: k, m: lt.indexOf(s.toLowerCase()) >= 0 ? 1 : 0 }; });
    sk.sort(function (a, b) { return b.m - a.m || a.k - b.k; });
    out.skills = sk.map(function (x) { return x.s; });
    out.matchedSkills = sk.filter(function (x) { return x.m; }).map(function (x) { return x.s; });

    var have = {};
    wordsOf(resumeWords(res)).forEach(function (w) { have[w] = 1; });
    out.missing = top.filter(function (w) { return !have[w] && jw[w] >= 2; }).slice(0, 15);
    out.phrasesHit = phrases;
    return out;
  }

  function renderText(o) {
    var L = [];
    if (o.name) L.push(o.name);
    if (o.contact) L.push(o.contact);
    if (o.headline) L.push(o.headline);
    if (o.summary) L.push("", "SUMMARY", o.summary);
    if (o.skills.length) L.push("", "SKILLS", o.skills.join(", "));
    if (o.exp.length) {
      L.push("", "EXPERIENCE");
      o.exp.forEach(function (e) {
        L.push(e.head.join(" | "));
        e.bullets.forEach(function (b) { L.push("• " + b); });
        L.push("");
      });
    }
    if (o.edu.length) L.push("EDUCATION", o.edu.join("\n"), "");
    if (o.certs.length) L.push("CERTIFICATIONS", o.certs.join("\n"), "");
    return L.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
  }

  function renderHtml(o) {
    var h = [];
    h.push('<h1>' + esc(o.name) + '</h1>');
    if (o.contact) h.push('<div class="rc">' + esc(o.contact) + '</div>');
    if (o.headline) h.push('<div class="rh">' + esc(o.headline) + '</div>');
    if (o.summary) h.push('<h2>Summary</h2><p>' + esc(o.summary) + '</p>');
    if (o.skills.length) h.push('<h2>Skills</h2><p>' + o.skills.map(esc).join(' &bull; ') + '</p>');
    if (o.exp.length) {
      h.push('<h2>Experience</h2>');
      o.exp.forEach(function (e) {
        var t = e.head;
        h.push('<div class="re"><b>' + esc(t[0] || "") + '</b>' + (t[1] ? ', ' + esc(t[1]) : '') +
          '<span class="rd">' + esc(t.slice(2).join(' | ')) + '</span></div>');
        if (e.bullets.length) h.push('<ul>' + e.bullets.map(function (b) { return '<li>' + esc(b) + '</li>'; }).join('') + '</ul>');
      });
    }
    if (o.edu.length) h.push('<h2>Education</h2>' + o.edu.map(function (x) { return '<p>' + esc(x) + '</p>'; }).join(''));
    if (o.certs.length) h.push('<h2>Certifications</h2>' + o.certs.map(function (x) { return '<p>' + esc(x) + '</p>'; }).join(''));
    return h.join('');
  }

  function buildPrompt(masterText, job) {
    return "Tailor my resume to the job posting below.\n\nRules:\n" +
      "1. Keep every fact true. Do not invent employers, titles, dates, tools, numbers or credentials.\n" +
      "2. Use bullet points and clear section headings, not paragraphs.\n" +
      "3. Reorder and reword bullets so the ones that match this posting come first, and use the posting's own keywords where they are honestly true.\n" +
      "4. Never use em dashes, en dashes, or hyphens as punctuation. Rephrase instead.\n" +
      "5. After the resume, list any requirements in the posting that my resume does not cover.\n\n" +
      "JOB: " + (job.title || "") + (job.company ? " at " + job.company : "") + "\n\nPOSTING:\n" + (job.text || "") +
      "\n\nMY MASTER RESUME:\n" + masterText + "\n";
  }

  var api = { parseResume: parseResume, tailor: tailor, renderText: renderText, renderHtml: renderHtml, buildPrompt: buildPrompt, wordsOf: wordsOf };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Resume = api;
})(typeof window !== "undefined" ? window : globalThis);
