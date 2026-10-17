import assert from "node:assert/strict";
import { extractSurveys, judgmentQuery } from "../lib/survey.ts";

const hits = extractSurveys(
  "Khatha No. 30, Sy.No. 28/2, Hoodi Village, Whitefield Main Road, K.R. Puram Hobli, Bangalore East Taluk, Bangalore.",
);
assert.equal(hits[0]?.number, "28/2");
assert.match(hits[0]?.village ?? "", /Hoodi/i);

const many = extractSurveys("Khatha No. 365, Sy.No. 13/6, 14/1, 16/4 and 16/5 of Hoodi Village, Bangalore East");
assert.ok(many.some(hit => hit.number === "13/6"));
assert.ok(many.some(hit => hit.number === "16/5"));

const query = judgmentQuery(hits[0], "Bengaluru Urban", "Bengaluru East");
assert.match(query, /28\/2/);
assert.match(query, /Hoodi/);
assert.equal(extractSurveys("NA").length, 0);
console.log("survey tests ok");
