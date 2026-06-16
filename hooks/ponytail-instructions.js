#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { DEFAULT_MODE, normalizeMode, normalizePersistedMode } = require('./ponytail-config');

const INDEPENDENT_MODES = new Set(['review']);
const SKILL_PATH = path.join(__dirname, '..', '.agents', 'skills', 'ponytail', 'SKILL.md');

function filterSkillBodyForMode(body, mode) {
  const effectiveMode = normalizeMode(mode) || DEFAULT_MODE;
  const withoutFrontmatter = String(body || '').replace(/^---[\s\S]*?---\s*/, '');
  return withoutFrontmatter.split(/\r?\n/).filter((line) => {
    const tableLabel = line.match(/^\|\s*\*\*(.+?)\*\*\s*\|/);
    if (tableLabel) {
      const labelMode = normalizeMode(tableLabel[1].trim());
      if (labelMode) return labelMode === effectiveMode;
    }
    const exampleLabel = line.match(/^-\s*([^:]+):\s*/);
    if (exampleLabel) {
      const labelMode = normalizeMode(exampleLabel[1].trim());
      if (labelMode) return labelMode === effectiveMode;
    }
    return true;
  }).join('\n');
}

function getFallbackInstructions(mode) {
  return 'PONYTAIL MODE ACTIVE — level: ' + mode + '\n\n' +
    '## Persistence\nACTIVE EVERY RESPONSE. Switch: `/ponytail lite|full|ultra`.\n\n' +
    '## The ladder\n1. Does this need to exist? (YAGNI)\n2. Stdlib? Use it.\n3. Native platform feature? Use it.\n4. Already-installed dependency? Use it.\n5. One line? One line.\n6. Minimum code.\n\n' +
    '## Rules\nNo unrequested abstractions. No avoidable dependencies. Deletion > addition. Fewest files.\n' +
    'Mark simplifications with `ponytail:` comment.\n\n' +
    '## Output\nCode first. Then at most 3 lines: what was skipped, when to add.\n\n' +
    '## When NOT to be lazy\nInput validation, data-loss handling, security, accessibility.\n' +
    'Non-trivial logic leaves ONE runnable check.\n\n' +
    '## Boundaries\n"stop ponytail" / "normal mode": revert.';
}

function getPonytailInstructions(mode) {
  const configuredMode = normalizePersistedMode(mode) || DEFAULT_MODE;
  if (INDEPENDENT_MODES.has(configuredMode)) {
    return 'PONYTAIL MODE ACTIVE — level: ' + configuredMode;
  }
  const effectiveMode = normalizeMode(configuredMode) || DEFAULT_MODE;
  try {
    return 'PONYTAIL MODE ACTIVE — level: ' + effectiveMode + '\n\n' +
      filterSkillBodyForMode(fs.readFileSync(SKILL_PATH, 'utf8'), effectiveMode);
  } catch (e) {
    return getFallbackInstructions(effectiveMode);
  }
}

module.exports = { filterSkillBodyForMode, getFallbackInstructions, getPonytailInstructions };
