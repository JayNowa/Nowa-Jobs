// Run with: node tests/resume.test.js
const assert = require("assert");
const R = require("../docs/resume.js");

const master = `Pat Example
pat@example.com | 555 0100 | Springfield, ST
# SUMMARY
HR professional with ten years across manufacturing and healthcare.
# SKILLS
Employee relations, HRIS administration, FMLA, Recruiting, Payroll, Excel
# EXPERIENCE
HR Generalist | Acme Corp | Springfield, ST | 2019 to 2024
- Administered FMLA and state leave across multiple states
- Planned the office holiday party
- Configured and maintained the HRIS and ran weekly payroll reports
- Led full cycle recruiting for 25 open requisitions
Recruiter | Beta Inc | Springfield, ST | 2014 to 2019
- Sourced candidates for healthcare roles
- Managed vendor relationships
# EDUCATION
BA Business, State University
# CERTIFICATIONS
SHRM-SCP
`;

const res = R.parseResume(master);
assert.strictEqual(res.name, "Pat Example");
assert.strictEqual(res.exp.length, 2);
assert.strictEqual(res.exp[0].bullets.length, 4);
assert.strictEqual(res.skills.length, 6);
assert.strictEqual(res.certs[0], "SHRM-SCP");

const cfg = { positive_terms: { fmla: 4, "full cycle": 3 }, roles: { Leave: ["leave", "fmla"] } };
const job = { title: "Leave Specialist (US)", company: "Lockton", text: "Administer FMLA and state leave. Leave administration, FMLA eligibility, leave compliance, payroll coordination, leave tracking system." };
const out = R.tailor(res, job, cfg);

assert.strictEqual(out.headline, "Leave Specialist");
assert.ok(out.exp[0].bullets[0].indexOf("FMLA") >= 0, "leave bullet should rank first");
assert.ok(out.exp[0].bullets.indexOf("Planned the office holiday party") > 0, "irrelevant bullet should not lead");
assert.ok(out.matchedSkills.indexOf("FMLA") >= 0);
assert.strictEqual(out.skills[0], "FMLA", "matched skills come first");
// never invents: every output bullet exists in the master
const all = res.exp.flatMap((e) => e.bullets);
out.exp.forEach((e) => e.bullets.forEach((b) => assert.ok(all.indexOf(b) >= 0)));
assert.ok(R.renderText(out).indexOf("• ") > 0);
assert.ok(R.renderHtml(out).indexOf("<ul>") > 0);
assert.ok(R.buildPrompt(master, job).indexOf("MY MASTER RESUME") > 0);
assert.ok(R.renderHtml(R.parseResume("<b>x</b>")).indexOf("<b>x</b>") < 0, "html is escaped");
console.log("resume tests ok");
