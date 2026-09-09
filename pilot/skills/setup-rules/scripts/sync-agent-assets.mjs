#!/usr/bin/env node

/**
 * Keep repository-owned agent instructions portable across Codex and Claude Code.
 *
 * Convention:
 *   AGENTS.md                 canonical shared instructions
 *   CLAUDE.md                 exactly "@AGENTS.md\n"
 *   .agents/skills/<name>/    Codex repository skills
 *   .claude/skills/<name>/    Claude Code repository skills
 *   .claude/skills/.pilot-sync-manifest.json  last converged ownership baseline
 *
 * Existing repositories may instead use an exact in-repository symlink between
 * the two instruction files or between the two skill roots. Those layouts
 * already share one physical source and are verified without mirror writes.
 *
 * Tracked skills retain .agents/skills as their durable source, while edits on
 * either side synchronize through the ownership baseline. Untracked and
 * gitignored skills synchronize in both directions through a trusted baseline
 * stored under .git/pilot; first-time one-sided skills are copied, independent
 * two-sided edits fail without overwriting either version.
 */

import {
  chmod,
  copyFile,
  lstat,
  mkdir,
  readdir,
  readFile,
  realpath,
  rename,
  rm,
  rmdir,
  unlink,
  writeFile,
} from 'node:fs/promises'
import { constants as fsConstants } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const CLAUDE_IMPORT = '@AGENTS.md\n'
const INSTALLED_PATH = path.join('scripts', 'sync-agent-assets.mjs')
const OWNERSHIP_MANIFEST = '.pilot-sync-manifest.json'
const OWNERSHIP_MANIFEST_PATH = `.claude/skills/${OWNERSHIP_MANIFEST}`
const LOCAL_PROVENANCE_GIT_PATH = 'pilot/sync-agent-assets.json'
const LOCAL_SKILL_PROVENANCE_GIT_PATH = 'pilot/sync-local-skills.json'
const SKILL_NAME_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
const MAX_SKILL_NAME_LENGTH = 64

class UsageError extends Error {}

function usage() {
  return [
    'Usage:',
    '  sync-agent-assets.mjs --check [--repo <path>]',
    '  sync-agent-assets.mjs --write [--force-migration] [--repo <path>]',
    '  sync-agent-assets.mjs --install [--force-migration] [--repo <path>]',
  ].join('\n')
}

function parseArgs(argv) {
  let mode = null
  let repo = null
  let forceMigration = false

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--check' || arg === '--write' || arg === '--install') {
      if (mode !== null) throw new UsageError('choose exactly one mode')
      mode = arg.slice(2)
      continue
    }
    if (arg === '--repo') {
      index += 1
      if (index >= argv.length || argv[index].startsWith('--')) {
        throw new UsageError('--repo requires a path')
      }
      repo = argv[index]
      continue
    }
    if (arg === '--force-migration') {
      if (forceMigration) throw new UsageError('--force-migration may only be provided once')
      forceMigration = true
      continue
    }
    if (arg.startsWith('--repo=')) {
      if (repo !== null) throw new UsageError('--repo may only be provided once')
      repo = arg.slice('--repo='.length)
      if (repo.length === 0) throw new UsageError('--repo requires a path')
      continue
    }
    if (arg === '--help' || arg === '-h') return { help: true }
    throw new UsageError(`unknown argument: ${arg}`)
  }

  if (mode === null) throw new UsageError('a mode is required')
  if (forceMigration && mode === 'check') {
    throw new UsageError('--force-migration is only valid with --write or --install')
  }
  return { help: false, mode, repo: path.resolve(repo ?? process.cwd()), forceMigration }
}

async function inspect(candidate) {
  try {
    return await lstat(candidate)
  } catch (error) {
    if (error?.code === 'ENOENT') return null
    throw error
  }
}

async function usesExactSharedPathPair(roots, kind) {
  const infos = await Promise.all(roots.map(root => inspect(root)))
  const linkedIndexes = infos.flatMap((info, index) => (info?.isSymbolicLink() ? [index] : []))
  if (linkedIndexes.length !== 1) return false

  const linkedIndex = linkedIndexes[0]
  const targetIndex = linkedIndex === 0 ? 1 : 0
  const targetInfo = infos[targetIndex]
  const targetMatches = kind === 'directory' ? targetInfo?.isDirectory() : targetInfo?.isFile()
  if (!targetMatches || targetInfo.isSymbolicLink()) return false

  try {
    const [linkedRealpath, targetRealpath] = await Promise.all([
      realpath(roots[linkedIndex]),
      realpath(roots[targetIndex]),
    ])
    return linkedRealpath === targetRealpath
  } catch {
    return false
  }
}

async function usesSharedSkillRoot(repo) {
  return usesExactSharedPathPair(
    [path.join(repo, '.agents', 'skills'), path.join(repo, '.claude', 'skills')],
    'directory',
  )
}

async function usesSharedInstructions(repo) {
  return usesExactSharedPathPair([path.join(repo, 'AGENTS.md'), path.join(repo, 'CLAUDE.md')], 'file')
}

function generatedInstructionSource(contents, expectedTarget) {
  const header = contents.split(/\r?\n/).slice(0, 16).join('\n')
  if (!/GENERATED FILE[^\n]*DO NOT EDIT/i.test(header)) return null
  const source = header.match(/\bSource:\s*([^|\r\n]+)/i)?.[1]?.trim()
  const target = header.match(/\bTarget:\s*([^|\r\n]+)/i)?.[1]?.trim()
  if (!source || target !== expectedTarget) return null
  return source
}

async function usesExternalGeneratedInstructions(repo) {
  const agents = path.join(repo, 'AGENTS.md')
  const claude = path.join(repo, 'CLAUDE.md')
  const [agentsInfo, claudeInfo] = await Promise.all([inspect(agents), inspect(claude)])
  if (
    !agentsInfo?.isFile() ||
    agentsInfo.isSymbolicLink() ||
    !claudeInfo?.isFile() ||
    claudeInfo.isSymbolicLink()
  ) {
    return false
  }
  const [agentsContents, claudeContents] = await Promise.all([
    readFile(agents, 'utf8'),
    readFile(claude, 'utf8'),
  ])
  const agentsSource = generatedInstructionSource(agentsContents, 'AGENTS.md')
  const claudeSource = generatedInstructionSource(claudeContents, 'CLAUDE.md')
  return agentsSource !== null && agentsSource === claudeSource
}

async function assertSafeRepoLayout(repo, { includeInstallerDestination = false } = {}) {
  const [sharedSkillRoot, sharedInstructions] = await Promise.all([
    usesSharedSkillRoot(repo),
    usesSharedInstructions(repo),
  ])
  const components = [
    ['AGENTS.md'],
    ['CLAUDE.md'],
    ['.agents'],
    ['.agents', 'skills'],
    ['.claude'],
    ['.claude', 'skills'],
    ['.claude', 'skills', OWNERSHIP_MANIFEST],
    ['.claude', 'rules'],
  ]
  if (includeInstallerDestination) {
    components.push(['scripts'], INSTALLED_PATH.split(path.sep))
  }

  for (const segments of components) {
    const candidate = path.join(repo, ...segments)
    const info = await inspect(candidate)
    if (info?.isSymbolicLink()) {
      const repositoryPath = segments.join('/')
      if (sharedSkillRoot && (repositoryPath === '.agents/skills' || repositoryPath === '.claude/skills')) {
        continue
      }
      if (sharedInstructions && (repositoryPath === 'AGENTS.md' || repositoryPath === 'CLAUDE.md')) {
        continue
      }
      throw new Error(`refusing symlinked repository path: ${segments.join('/')}`)
    }
  }
  return { sharedSkillRoot, sharedInstructions }
}

async function sharedRootSkills(repo) {
  const root = path.join(repo, '.claude', 'skills')
  const entries = await readdir(root, { withFileTypes: true })
  return entries
    .filter(entry => !entry.name.startsWith('.') && entry.isDirectory())
    .sort((left, right) => left.name.localeCompare(right.name))
    .map(entry => ({ name: entry.name, sourceRoot: root }))
}

async function discoverRuleFiles(repo) {
  const rulesRoot = path.join(repo, '.claude', 'rules')
  const rootInfo = await inspect(rulesRoot)
  if (rootInfo === null) return []
  if (!rootInfo.isDirectory()) throw new Error('.claude/rules must be a directory')

  const rules = []
  async function visit(directory) {
    const entries = await readdir(directory, { withFileTypes: true })
    for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
      const candidate = path.join(directory, entry.name)
      const candidateRelative = relative(repo, candidate)
      const info = await lstat(candidate)
      if (info.isSymbolicLink()) {
        throw new Error(`refusing symlinked repository rule path: ${candidateRelative}`)
      }
      if (info.isDirectory()) {
        await visit(candidate)
      } else if (info.isFile() && entry.name.endsWith('.md') && entry.name !== 'README.md') {
        if (!isGitIgnored(repo, candidateRelative)) rules.push(candidateRelative)
      }
    }
  }

  await visit(rulesRoot)
  return rules.sort()
}

function extractRuleReferences(agentsContents) {
  const references = new Set()
  const patterns = [
    /`(\.claude\/rules\/[^`\n]+?\.md)(?:#[^`\n]*)?`/g,
    /\((\.claude\/rules\/[^)\n]+?\.md)(?:#[^)\n]*)?\)/g,
    /\.claude\/rules\/[A-Za-z0-9._~%+@/-]+\.md(?=$|[\s`"'()<>{}\[\],:;#])/g,
  ]
  for (const pattern of patterns) {
    for (const match of agentsContents.matchAll(pattern)) {
      const reference = match[1] ?? match[0]
      if (match[1] === undefined && (match.index ?? 0) > 0) {
        const preceding = agentsContents[(match.index ?? 0) - 1]
        if (/[A-Za-z0-9_~$./-]/.test(preceding)) continue
      }
      if (!/[?*\[\]{}]/.test(reference)) references.add(reference)
    }
  }
  return [...references].sort()
}

async function auditRuleRouting(repo, agentsContents) {
  const rules = await discoverRuleFiles(repo)
  const references = extractRuleReferences(agentsContents)
  const issues = []

  for (const rule of rules) {
    if (!references.includes(rule)) {
      issues.push(`AGENTS.md is missing exact rule reference: ${rule}; add this path to the rule index`)
    }
  }

  const rulesRoot = path.resolve(repo, '.claude', 'rules')
  for (const reference of references) {
    const candidate = path.resolve(repo, ...reference.split('/'))
    if (candidate !== rulesRoot && !candidate.startsWith(`${rulesRoot}${path.sep}`)) {
      issues.push(`AGENTS.md has invalid rule reference outside .claude/rules: ${reference}; remove it`)
      continue
    }
    const info = await inspect(candidate)
    if (info === null || !info.isFile() || info.isSymbolicLink()) {
      issues.push(`AGENTS.md references missing rule file: ${reference}; update or remove the stale reference`)
    }
  }
  return issues
}

function relative(repo, candidate) {
  return path.relative(repo, candidate).split(path.sep).join('/') || '.'
}

async function assetRecord(asset) {
  if (asset?.kind !== 'file') return null
  const bytes = await readFile(asset.absolute)
  return {
    sha256: createHash('sha256').update(bytes).digest('hex'),
    // Git preserves only whether a file is executable, while checkout umasks
    // decide which of the three execute bits appear on disk. Store that
    // portable capability instead of a machine-specific permission mask.
    executableMode: asset.info.mode & 0o111 ? 0o111 : 0,
  }
}

function recordsEqual(left, right) {
  return (
    left !== null &&
    right !== null &&
    left.sha256 === right.sha256 &&
    left.executableMode === right.executableMode
  )
}

function comparePaths(left, right) {
  return left < right ? -1 : left > right ? 1 : 0
}

function serializeOwnershipManifest(files) {
  const sortedFiles = Object.fromEntries([...files.entries()].sort(([left], [right]) => comparePaths(left, right)))
  return `${JSON.stringify({ version: 1, files: sortedFiles }, null, 2)}\n`
}

function parseOwnershipManifest(raw, label) {
  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error(`${label} contains invalid JSON; inspect or remove it before syncing`)
  }
  if (parsed?.version !== 1 || parsed.files === null || typeof parsed.files !== 'object' || Array.isArray(parsed.files)) {
    throw new Error(`${label} has an unsupported schema; inspect or remove it before syncing`)
  }

  const files = new Map()
  for (const [assetPath, record] of Object.entries(parsed.files)) {
    const parts = assetPath.split('/')
    const normalized = path.posix.normalize(assetPath)
    const validPath =
      parts.length >= 2 &&
      normalized === assetPath &&
      !path.posix.isAbsolute(assetPath) &&
      !parts.includes('..') &&
      assetPath !== OWNERSHIP_MANIFEST
    const validRecord =
      record !== null &&
      typeof record === 'object' &&
      !Array.isArray(record) &&
      /^[a-f0-9]{64}$/.test(record.sha256) &&
      Number.isInteger(record.executableMode) &&
      (record.executableMode === 0 || record.executableMode === 0o111)
    if (!validPath || !validRecord) {
      throw new Error(`${label} has an invalid managed entry: ${assetPath}`)
    }
    files.set(assetPath, {
      sha256: record.sha256,
      executableMode: record.executableMode,
    })
  }

  return { exists: true, files, canonical: raw === serializeOwnershipManifest(files) }
}

async function loadOwnershipManifest(repo) {
  const manifestPath = path.join(repo, ...OWNERSHIP_MANIFEST_PATH.split('/'))
  const info = await inspect(manifestPath)
  if (info === null) return { exists: false, files: new Map(), canonical: true }
  if (!info.isFile() || info.isSymbolicLink()) {
    throw new Error(`${OWNERSHIP_MANIFEST_PATH} must be a regular file`)
  }
  return parseOwnershipManifest(await readFile(manifestPath, 'utf8'), OWNERSHIP_MANIFEST_PATH)
}

function decodeFrontmatterScalar(value, lines, lineIndex, label, field) {
  if (/^[|>][+-]?$/.test(value)) {
    const block = []
    for (let index = lineIndex + 1; index < lines.length; index += 1) {
      const line = lines[index]
      if (line.length > 0 && !/^\s/.test(line)) break
      block.push(line)
    }
    value = block.join('\n').trim()
  } else if (value.startsWith('"')) {
    try {
      value = JSON.parse(value)
    } catch {
      throw new Error(`${label}: SKILL.md frontmatter has an invalid quoted ${field}`)
    }
  } else if (value.startsWith("'")) {
    if (!value.endsWith("'") || value.length < 2) {
      throw new Error(`${label}: SKILL.md frontmatter has an invalid quoted ${field}`)
    }
    value = value.slice(1, -1).replaceAll("''", "'")
  } else {
    value = value.replace(/(^|\s)#.*$/, '').trimEnd()
  }

  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`${label}: SKILL.md frontmatter ${field} must be a non-empty string`)
  }
  return value
}

function extractFrontmatterMetadata(contents, label) {
  const lines = contents.split(/\r?\n/)
  if (lines[0] !== '---') {
    throw new Error(`${label}: SKILL.md must start with YAML frontmatter`)
  }

  const closing = lines.indexOf('---', 1)
  if (closing === -1) {
    throw new Error(`${label}: SKILL.md frontmatter has no closing --- delimiter`)
  }

  const fields = new Map([
    ['name', []],
    ['description', []],
  ])
  for (let index = 1; index < closing; index += 1) {
    const line = lines[index]
    if (line.includes('\t')) {
      throw new Error(`${label}: SKILL.md frontmatter must not contain tabs`)
    }
    const match = /^(name|description)\s*:\s*(.*?)\s*$/.exec(line)
    if (match) fields.get(match[1]).push({ value: match[2], lineIndex: index })
  }

  if (fields.get('name').length !== 1) {
    throw new Error(`${label}: SKILL.md frontmatter must contain exactly one top-level name field`)
  }
  if (fields.get('description').length !== 1) {
    throw new Error(`${label}: SKILL.md frontmatter must contain exactly one top-level description field`)
  }

  const name = fields.get('name')[0]
  const description = fields.get('description')[0]
  return {
    name: decodeFrontmatterScalar(name.value, lines, name.lineIndex, label, 'name'),
    description: decodeFrontmatterScalar(
      description.value,
      lines,
      description.lineIndex,
      label,
      'description',
    ),
  }
}

function validateSkillName(name, label) {
  if (name.length > MAX_SKILL_NAME_LENGTH || !SKILL_NAME_PATTERN.test(name)) {
    throw new Error(
      `${label}: skill names must be 1-${MAX_SKILL_NAME_LENGTH} lowercase letters, numbers, or single hyphens`,
    )
  }
}

async function discoverSkills(repo) {
  const sourceRoot = path.join(repo, '.agents', 'skills')
  const sourceInfo = await inspect(sourceRoot)
  if (sourceInfo === null) return []
  if (!sourceInfo.isDirectory()) {
    throw new Error('.agents/skills must exist and be a directory')
  }

  const entries = await readdir(sourceRoot, { withFileTypes: true })
  const skills = []
  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
    if (entry.name.startsWith('.') || !entry.isDirectory()) continue

    const label = `.agents/skills/${entry.name}`
    const skillFileLabel = `${label}/SKILL.md`
    if (isGitIgnored(repo, skillFileLabel)) continue

    validateSkillName(entry.name, label)
    const skillRoot = path.join(sourceRoot, entry.name)
    const skillFile = path.join(skillRoot, 'SKILL.md')
    const skillInfo = await inspect(skillFile)
    if (skillInfo === null || !skillInfo.isFile()) {
      throw new Error(`${label}: SKILL.md is required`)
    }

    const { name: declaredName } = extractFrontmatterMetadata(await readFile(skillFile, 'utf8'), label)
    validateSkillName(declaredName, label)
    if (declaredName !== entry.name) {
      throw new Error(`${label}: frontmatter name ${JSON.stringify(declaredName)} must match the directory name`)
    }

    skills.push({ name: entry.name, sourceRoot })
  }
  return skills
}

function runGit(repo, args) {
  const result = spawnSync('git', ['-C', repo, ...args], {
    encoding: null,
    maxBuffer: 16 * 1024 * 1024,
  })
  if (result.error) {
    if (result.error.code === 'ENOENT') {
      throw new Error('git is required to distinguish tracked mirror assets from agent-local skills')
    }
    throw result.error
  }
  return result
}

function isGitIgnored(repo, candidate) {
  const result = runGit(repo, ['check-ignore', '--quiet', '--', candidate])
  if (result.status === 0) return true
  if (result.status === 1) return false
  const message = result.stderr.toString('utf8').trim()
  if (/not a git repository/i.test(message)) return false
  throw new Error(`git check-ignore failed: ${message}`)
}

function localProvenancePath(repo) {
  const result = runGit(repo, ['rev-parse', '--git-path', LOCAL_PROVENANCE_GIT_PATH])
  if (result.status !== 0) {
    const message = result.stderr.toString('utf8').trim()
    if (/not a git repository/i.test(message)) return null
    throw new Error(`git rev-parse --git-path failed: ${message}`)
  }
  const gitPath = result.stdout.toString('utf8').trim()
  if (!gitPath) throw new Error('git rev-parse --git-path returned an empty provenance path')
  return path.isAbsolute(gitPath) ? gitPath : path.resolve(repo, gitPath)
}

async function loadLocalProvenance(repo) {
  const provenancePath = localProvenancePath(repo)
  if (provenancePath === null) return { exists: false, files: new Map(), canonical: true, path: null }
  const info = await inspect(provenancePath)
  if (info === null || !info.isFile() || info.isSymbolicLink()) {
    return { exists: false, files: new Map(), canonical: true, path: provenancePath }
  }
  try {
    return {
      ...parseOwnershipManifest(await readFile(provenancePath, 'utf8'), 'trusted local provenance'),
      path: provenancePath,
    }
  } catch {
    return { exists: false, files: new Map(), canonical: false, path: provenancePath }
  }
}

function localSkillProvenancePath(repo) {
  const result = runGit(repo, ['rev-parse', '--git-path', LOCAL_SKILL_PROVENANCE_GIT_PATH])
  if (result.status !== 0) {
    const message = result.stderr.toString('utf8').trim()
    if (/not a git repository/i.test(message)) return null
    throw new Error(`git rev-parse --git-path failed: ${message}`)
  }
  const gitPath = result.stdout.toString('utf8').trim()
  if (!gitPath) throw new Error('git rev-parse --git-path returned an empty local-skill provenance path')
  return path.isAbsolute(gitPath) ? gitPath : path.resolve(repo, gitPath)
}

function serializeLocalSkillProvenance(skills) {
  return `${JSON.stringify(
    {
      version: 1,
      skills: Object.fromEntries([...skills.entries()].sort(([left], [right]) => comparePaths(left, right))),
    },
    null,
    2,
  )}\n`
}

async function loadLocalSkillProvenance(repo) {
  const provenancePath = localSkillProvenancePath(repo)
  if (provenancePath === null) return { path: null, skills: new Map() }
  const info = await inspect(provenancePath)
  if (info === null) return { path: provenancePath, skills: new Map() }
  if (!info.isFile() || info.isSymbolicLink()) {
    throw new Error('trusted local-skill provenance must be a regular file')
  }
  let parsed
  try {
    parsed = JSON.parse(await readFile(provenancePath, 'utf8'))
  } catch (error) {
    throw new Error(`trusted local-skill provenance is unreadable: ${error.message}`)
  }
  if (parsed?.version !== 1 || parsed.skills === null || typeof parsed.skills !== 'object' || Array.isArray(parsed.skills)) {
    throw new Error('trusted local-skill provenance has an unsupported schema')
  }
  const skills = new Map()
  for (const [name, digest] of Object.entries(parsed.skills)) {
    validateSkillName(name, 'trusted local-skill provenance')
    if (typeof digest !== 'string' || !/^[a-f0-9]{64}$/.test(digest)) {
      throw new Error(`trusted local-skill provenance has an invalid digest for ${name}`)
    }
    skills.set(name, digest)
  }
  return { path: provenancePath, skills }
}

async function skillDigest(skillRoot, name) {
  const tree = await collectTree(skillRoot, { rejectSymlinks: true })
  const skillFile = tree.files.get('SKILL.md')
  if (skillFile === undefined || skillFile.kind !== 'file') {
    throw new Error(`${relative(path.dirname(path.dirname(path.dirname(skillRoot))), skillRoot)}: SKILL.md is required`)
  }
  const label = relative(path.dirname(path.dirname(path.dirname(skillRoot))), skillRoot)
  const { name: declaredName } = extractFrontmatterMetadata(await readFile(skillFile.absolute, 'utf8'), label)
  validateSkillName(declaredName, label)
  if (declaredName !== name) {
    throw new Error(`${label}: frontmatter name ${JSON.stringify(declaredName)} must match the directory name`)
  }
  const digest = createHash('sha256')
  for (const [file, asset] of [...tree.files.entries()].sort(([left], [right]) => comparePaths(left, right))) {
    digest.update(file)
    digest.update('\0')
    digest.update(String(asset.info.mode & 0o111))
    digest.update('\0')
    digest.update(await readFile(asset.absolute))
    digest.update('\0')
  }
  return digest.digest('hex')
}

async function skillTreeContains(largerRoot, smallerRoot) {
  const [larger, smaller] = await Promise.all([
    collectTree(largerRoot, { rejectSymlinks: true }),
    collectTree(smallerRoot, { rejectSymlinks: true }),
  ])
  for (const [file, smallerAsset] of smaller.files) {
    const largerAsset = larger.files.get(file)
    if (largerAsset === undefined || !(await filesMatch(smallerAsset, largerAsset))) return false
  }
  return true
}

async function replaceSkillDirectory(source, destination) {
  const suffix = `${process.pid}-${Math.random().toString(16).slice(2)}`
  const temporary = `${destination}.pilot-sync-${suffix}`
  const backup = `${destination}.pilot-backup-${suffix}`
  await rm(temporary, { recursive: true, force: true })
  await rm(backup, { recursive: true, force: true })
  await mkdir(temporary, { recursive: true })
  const tree = await collectTree(source, { rejectSymlinks: true })
  for (const directory of [...tree.directories].sort()) {
    await mkdir(path.join(temporary, directory), { recursive: true })
  }
  for (const [file, asset] of tree.files) {
    await atomicCopy(asset.absolute, path.join(temporary, file), asset.info.mode)
  }

  const destinationInfo = await inspect(destination)
  try {
    if (destinationInfo !== null) await rename(destination, backup)
    await rename(temporary, destination)
    await rm(backup, { recursive: true, force: true })
  } catch (error) {
    if ((await inspect(destination)) === null && (await inspect(backup)) !== null) {
      await rename(backup, destination)
    }
    await rm(temporary, { recursive: true, force: true })
    throw error
  }
}

async function skillDirectories(root) {
  const info = await inspect(root)
  if (info === null) return new Map()
  if (!info.isDirectory() || info.isSymbolicLink()) {
    throw new Error(`${root}: skill root must be a regular directory`)
  }
  const entries = new Map()
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue
    entries.set(entry.name, path.join(root, entry.name))
  }
  return entries
}

function hasTrackedSkillAssets(repo, name) {
  const result = runGit(repo, [
    'ls-files',
    '-z',
    '--',
    `.agents/skills/${name}`,
    `.claude/skills/${name}`,
  ])
  if (result.status !== 0) return false
  return result.stdout.length > 0
}

async function discoverIgnoredSkillPairs(repo) {
  const canonicalRoot = path.join(repo, '.agents', 'skills')
  const mirrorRoot = path.join(repo, '.claude', 'skills')
  const [canonicalEntries, mirrorEntries] = await Promise.all([
    skillDirectories(canonicalRoot),
    skillDirectories(mirrorRoot),
  ])
  const names = new Set([...canonicalEntries.keys(), ...mirrorEntries.keys()])
  const pairs = []
  for (const name of [...names].sort()) {
    validateSkillName(name, `local skill ${name}`)
    const canonical = canonicalEntries.get(name) ?? path.join(canonicalRoot, name)
    const mirror = mirrorEntries.get(name) ?? path.join(mirrorRoot, name)
    const [canonicalInfo, mirrorInfo] = await Promise.all([inspect(canonical), inspect(mirror)])

    if (mirrorInfo?.isSymbolicLink() && canonicalInfo?.isDirectory() && !canonicalInfo.isSymbolicLink()) {
      if ((await realpath(mirror)) === (await realpath(canonical))) continue
    }
    if (canonicalInfo?.isSymbolicLink() || mirrorInfo?.isSymbolicLink()) {
      throw new Error(`local skill ${name}: symbolic links must point from the Claude mirror to its canonical skill`)
    }
    if (canonicalInfo !== null && !canonicalInfo.isDirectory()) {
      throw new Error(`.agents/skills/${name}: skill must be a directory`)
    }
    if (mirrorInfo !== null && !mirrorInfo.isDirectory()) {
      throw new Error(`.claude/skills/${name}: skill must be a directory`)
    }
    const tracked = hasTrackedSkillAssets(repo, name)
    if (tracked && canonicalInfo !== null && mirrorInfo !== null) continue

    const [canonicalSkillFile, mirrorSkillFile] = await Promise.all([
      inspect(path.join(canonical, 'SKILL.md')),
      inspect(path.join(mirror, 'SKILL.md')),
    ])
    if (canonicalSkillFile === null && mirrorSkillFile === null) continue
    if (canonicalInfo === null || mirrorInfo === null) {
      const existingFile = canonicalInfo === null ? mirrorSkillFile : canonicalSkillFile
      const existingRoot = canonicalInfo === null ? mirror : canonical
      if (existingFile === null || !existingFile.isFile() || existingFile.isSymbolicLink()) continue
      try {
        extractFrontmatterMetadata(await readFile(path.join(existingRoot, 'SKILL.md'), 'utf8'), `local skill ${name}`)
      } catch {
        // A one-sided directory without valid skill metadata is private agent
        // state, not a portable skill. Preserve it without blocking all sync.
        continue
      }
    }

    pairs.push({ name, canonical, mirror, canonicalInfo, mirrorInfo })
  }
  return pairs
}

async function validatePairedMirrorSkills(repo) {
  const canonicalRoot = path.join(repo, '.agents', 'skills')
  const mirrorRoot = path.join(repo, '.claude', 'skills')
  const mirrors = await skillDirectories(mirrorRoot)
  for (const [name, mirror] of mirrors) {
    const canonical = path.join(canonicalRoot, name)
    const [canonicalInfo, mirrorInfo, mirrorSkill] = await Promise.all([
      inspect(canonical),
      inspect(mirror),
      inspect(path.join(mirror, 'SKILL.md')),
    ])
    if (canonicalInfo === null || mirrorSkill === null) continue
    if (mirrorInfo?.isSymbolicLink() && canonicalInfo.isDirectory() && !canonicalInfo.isSymbolicLink()) {
      if ((await realpath(mirror)) === (await realpath(canonical))) continue
    }
    await skillDigest(mirror, name)
  }
}

async function planIgnoredSkillSync(repo) {
  const provenance = await loadLocalSkillProvenance(repo)
  const pairs = await discoverIgnoredSkillPairs(repo)
  const actions = []
  const issues = []
  const finalDigests = new Map()

  for (const pair of pairs) {
    const canonicalDigest = pair.canonicalInfo === null ? null : await skillDigest(pair.canonical, pair.name)
    const mirrorDigest = pair.mirrorInfo === null ? null : await skillDigest(pair.mirror, pair.name)
    const baseline = provenance.skills.get(pair.name)

    if (canonicalDigest === null || mirrorDigest === null) {
      const existingPath = canonicalDigest === null ? pair.mirror : pair.canonical
      const missingPath = canonicalDigest === null ? pair.canonical : pair.mirror
      const existingDigest = canonicalDigest ?? mirrorDigest
      if (baseline === undefined) {
        actions.push({ type: 'replace', source: existingPath, destination: missingPath })
        finalDigests.set(pair.name, existingDigest)
      } else if (existingDigest === baseline) {
        actions.push({ type: 'delete', destination: existingPath })
      } else {
        issues.push(`local skill ${pair.name}: one side was deleted while the other changed; preserved both states`)
      }
      continue
    }

    if (canonicalDigest === mirrorDigest) {
      finalDigests.set(pair.name, canonicalDigest)
      continue
    }
    if (baseline === undefined) {
      if (await skillTreeContains(pair.mirror, pair.canonical)) {
        actions.push({ type: 'replace', source: pair.mirror, destination: pair.canonical })
        finalDigests.set(pair.name, mirrorDigest)
      } else if (await skillTreeContains(pair.canonical, pair.mirror)) {
        actions.push({ type: 'replace', source: pair.canonical, destination: pair.mirror })
        finalDigests.set(pair.name, canonicalDigest)
      } else {
        issues.push(`local skill ${pair.name}: both sides differ without a trusted baseline; preserved both versions`)
      }
    } else if (canonicalDigest === baseline && mirrorDigest !== baseline) {
      actions.push({ type: 'replace', source: pair.mirror, destination: pair.canonical })
      finalDigests.set(pair.name, mirrorDigest)
    } else if (mirrorDigest === baseline && canonicalDigest !== baseline) {
      actions.push({ type: 'replace', source: pair.canonical, destination: pair.mirror })
      finalDigests.set(pair.name, canonicalDigest)
    } else {
      issues.push(`local skill ${pair.name}: both sides changed; preserved both versions`)
    }
  }

  return { provenance, actions, issues, finalDigests }
}

async function auditIgnoredSkills(repo) {
  const plan = await planIgnoredSkillSync(repo)
  return [
    ...plan.issues,
    ...plan.actions.map(action => {
      const destination = relative(repo, action.destination)
      if (action.type === 'delete') return `${destination}: local skill deletion has not synchronized`
      const side = destination.startsWith('.agents/') ? 'Codex' : 'Claude'
      return `${destination}: missing ${side} counterpart or local skill drift`
    }),
  ]
}

async function synchronizeIgnoredSkills(repo) {
  const plan = await planIgnoredSkillSync(repo)
  if (plan.issues.length > 0) throw new Error(plan.issues.join('\n'))
  for (const action of plan.actions) {
    if (action.type === 'replace') {
      await replaceSkillDirectory(action.source, action.destination)
    } else {
      await rm(action.destination, { recursive: true, force: true })
    }
  }
  if (plan.provenance.path !== null) {
    await atomicWriteText(
      plan.provenance.path,
      serializeLocalSkillProvenance(plan.finalDigests),
      0o600,
    )
  }
}

async function synchronizeRootInstructions(repo) {
  const agents = path.join(repo, 'AGENTS.md')
  const claude = path.join(repo, 'CLAUDE.md')
  const [agentsInfo, claudeInfo] = await Promise.all([inspect(agents), inspect(claude)])
  if (agentsInfo === null && claudeInfo === null) return
  if (agentsInfo !== null && (!agentsInfo.isFile() || agentsInfo.isSymbolicLink())) {
    throw new Error('AGENTS.md must be a regular file')
  }
  if (claudeInfo !== null && (!claudeInfo.isFile() || claudeInfo.isSymbolicLink())) {
    throw new Error('CLAUDE.md must be a regular file')
  }

  if (agentsInfo === null) {
    const claudeContents = await readFile(claude, 'utf8')
    if (claudeContents === CLAUDE_IMPORT) {
      throw new Error('CLAUDE.md imports AGENTS.md, but AGENTS.md is missing')
    }
    await atomicWriteText(agents, claudeContents, 0o644)
    await atomicWriteText(claude, CLAUDE_IMPORT, 0o644)
    return
  }

  if (claudeInfo === null) {
    await atomicWriteText(claude, CLAUDE_IMPORT, 0o644)
    return
  }
  const claudeContents = await readFile(claude, 'utf8')
  if (claudeContents !== CLAUDE_IMPORT) {
    if (isTrivialClaude(claudeContents)) {
      await atomicWriteText(claude, CLAUDE_IMPORT, 0o644)
      return
    }
    throw new Error(
      'refusing to overwrite nontrivial CLAUDE.md; AGENTS.md and CLAUDE.md both contain instructions, so both were preserved for explicit reconciliation',
    )
  }
}

function isIgnoredCanonicalAsset(repo, assetPath) {
  const skillName = assetPath.split('/')[0]
  return Boolean(skillName) && isGitIgnored(repo, `.agents/skills/${skillName}/SKILL.md`)
}

function trackedSkillAssets(repo) {
  const worktree = runGit(repo, ['rev-parse', '--is-inside-work-tree'])
  if (worktree.status !== 0) {
    const message = worktree.stderr.toString('utf8').trim()
    if (/not a git repository/i.test(message)) return new Set()
    throw new Error(`git rev-parse failed: ${message}`)
  }

  const tracked = runGit(repo, ['ls-files', '-z', '--', '.claude/skills'])
  if (tracked.status !== 0) {
    throw new Error(`git ls-files failed: ${tracked.stderr.toString('utf8').trim()}`)
  }

  const assets = new Set(
    tracked.stdout
      .toString('utf8')
      .split('\0')
      .filter(candidate => candidate === '.claude/skills' || candidate.startsWith('.claude/skills/'))
      .map(candidate => candidate.split(path.sep).join('/')),
  )
  assets.delete(OWNERSHIP_MANIFEST_PATH)
  return assets
}

async function trackedMirrorOnlyAssets(repo, canonicalNames, trackedAssets) {
  const prefix = '.claude/skills/'
  const assets = []
  for (const normalized of [...trackedAssets].sort()) {
    if (!normalized.startsWith(prefix)) continue
    const remainder = normalized.slice(prefix.length)
    const skillName = remainder.split('/')[0]
    if (!skillName || canonicalNames.has(skillName)) continue

    const absolute = path.join(repo, ...normalized.split('/'))
    if ((await inspect(absolute)) !== null) assets.push({ absolute, relative: normalized })
  }
  return assets
}

async function collectTree(root, { rejectSymlinks = false } = {}) {
  const files = new Map()
  const directories = new Set()

  async function visit(current, currentRelative) {
    const entries = await readdir(current, { withFileTypes: true })
    for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
      const absolute = path.join(current, entry.name)
      const itemRelative = currentRelative ? path.join(currentRelative, entry.name) : entry.name
      const normalized = itemRelative.split(path.sep).join('/')
      const info = await lstat(absolute)

      if (info.isSymbolicLink()) {
        if (rejectSymlinks) throw new Error(`${normalized}: symbolic links are not portable skill assets`)
        files.set(normalized, { absolute, info, kind: 'symlink' })
      } else if (info.isDirectory()) {
        directories.add(normalized)
        await visit(absolute, itemRelative)
      } else if (info.isFile()) {
        files.set(normalized, { absolute, info, kind: 'file' })
      } else {
        throw new Error(`${normalized}: unsupported filesystem entry`)
      }
    }
  }

  await visit(root, '')
  return { files, directories }
}

function hasTrackedPath(trackedAssets, candidate) {
  if (trackedAssets.has(candidate)) return true
  const prefix = `${candidate}/`
  return [...trackedAssets].some(tracked => tracked.startsWith(prefix))
}

function hasManifestPath(manifestFiles, candidate) {
  if (manifestFiles.has(candidate)) return true
  const prefix = `${candidate}/`
  return [...manifestFiles.keys()].some(managed => managed.startsWith(prefix))
}

function canonicalPathForMirror(mirrorPath) {
  return mirrorPath.replace(/^\.claude\/skills(?=\/|$)/, '.agents/skills')
}

async function compareSkill(repo, name, sourceRoot, targetRoot, trackedAssets) {
  const sourceSkill = path.join(sourceRoot, name)
  const targetSkill = path.join(targetRoot, name)
  const issues = []
  const targetInfo = await inspect(targetSkill)
  const sourceTree = await collectTree(sourceSkill, { rejectSymlinks: true })

  if (targetInfo === null || !targetInfo.isDirectory() || targetInfo.isSymbolicLink()) {
    issues.push(`${relative(repo, targetSkill)}: missing mirrored skill directory`)
    return issues
  }

  const targetTree = await collectTree(targetSkill)
  for (const [file, source] of sourceTree.files) {
    const destination = targetTree.files.get(file)
    const label = relative(repo, path.join(targetSkill, file))
    if (destination === undefined || destination.kind !== 'file') {
      issues.push(`${label}: missing mirrored file`)
      continue
    }

    const [sourceBytes, targetBytes] = await Promise.all([
      readFile(source.absolute),
      readFile(destination.absolute),
    ])
    if (!sourceBytes.equals(targetBytes)) issues.push(`${label}: bytes differ`)
    if ((source.info.mode & 0o111) !== (destination.info.mode & 0o111)) {
      issues.push(`${label}: executable bits differ`)
    }
  }

  for (const [file] of targetTree.files) {
    const label = relative(repo, path.join(targetSkill, file))
    if (!sourceTree.files.has(file) && trackedAssets.has(label)) {
      issues.push(`${label}: extra tracked mirrored file; migrate to ${canonicalPathForMirror(label)}`)
    }
  }
  for (const directory of targetTree.directories) {
    const label = relative(repo, path.join(targetSkill, directory))
    if (!sourceTree.directories.has(directory) && hasTrackedPath(trackedAssets, label)) {
      issues.push(`${label}: extra tracked mirrored directory; migrate to ${canonicalPathForMirror(label)}`)
    }
  }

  return issues
}

async function audit(repo) {
  const { sharedSkillRoot, sharedInstructions } = await assertSafeRepoLayout(repo)
  const externalGeneratedInstructions =
    !sharedInstructions && (await usesExternalGeneratedInstructions(repo))
  const agents = path.join(repo, 'AGENTS.md')
  const agentsInfo = await inspect(agents)
  if (agentsInfo !== null && !sharedInstructions && (!agentsInfo.isFile() || agentsInfo.isSymbolicLink())) {
    throw new Error('AGENTS.md must be a regular file')
  }
  const agentsContents = agentsInfo === null ? '' : await readFile(agents, 'utf8')

  const skills = sharedSkillRoot ? await sharedRootSkills(repo) : await discoverSkills(repo)
  const trackedAssets = sharedSkillRoot ? new Set() : trackedSkillAssets(repo)
  const targetRoot = path.join(repo, '.claude', 'skills')
  const manifest = sharedSkillRoot
    ? { exists: false, files: new Map(), canonical: true }
    : await loadOwnershipManifest(repo)
  const issues = [
    ...(sharedSkillRoot ? [] : await auditIgnoredSkills(repo)),
    ...(await auditRuleRouting(repo, agentsContents)),
    ...(sharedSkillRoot ? [] : await auditOwnershipManifest(repo, skills, targetRoot, manifest)),
  ]
  const claude = path.join(repo, 'CLAUDE.md')
  const claudeInfo = await inspect(claude)
  if (!sharedInstructions && !externalGeneratedInstructions) {
    if (agentsInfo === null && claudeInfo !== null) {
      issues.push('AGENTS.md: missing; migrate the existing CLAUDE.md instructions')
    } else if (agentsInfo !== null && claudeInfo === null) {
      issues.push('CLAUDE.md: missing; expected exactly @AGENTS.md')
    } else if (agentsInfo !== null && (await readFile(claude, 'utf8')) !== CLAUDE_IMPORT) {
      issues.push('CLAUDE.md: content differs; expected exactly @AGENTS.md')
    }
  }

  if (!sharedSkillRoot) {
    for (const skill of skills) {
      issues.push(...(await compareSkill(repo, skill.name, skill.sourceRoot, targetRoot, trackedAssets)))
    }
    const canonicalNames = new Set(skills.map(skill => skill.name))
    for (const asset of await trackedMirrorOnlyAssets(repo, canonicalNames, trackedAssets)) {
      issues.push(
        `${asset.relative}: tracked mirror-only asset has no canonical source; migrate to ${canonicalPathForMirror(asset.relative)}`,
      )
    }
  }
  return { issues, skills }
}

function isTrivialClaude(contents) {
  const meaningful = contents
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean)
  return meaningful.length === 0 || (meaningful.length === 1 && meaningful[0] === '@AGENTS.md')
}

async function atomicCopy(source, destination, mode) {
  await mkdir(path.dirname(destination), { recursive: true })
  const temporary = `${destination}.pilot-sync-${process.pid}-${Math.random().toString(16).slice(2)}`
  try {
    await copyFile(source, temporary, fsConstants.COPYFILE_FICLONE)
    await chmod(temporary, mode & 0o777)
    await rename(temporary, destination)
  } finally {
    try {
      await unlink(temporary)
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error
    }
  }
}

async function atomicWriteText(destination, contents, mode) {
  await mkdir(path.dirname(destination), { recursive: true })
  const temporary = `${destination}.pilot-sync-${process.pid}-${Math.random().toString(16).slice(2)}`
  try {
    await writeFile(temporary, contents, 'utf8')
    await chmod(temporary, mode)
    await rename(temporary, destination)
  } finally {
    try {
      await unlink(temporary)
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error
    }
  }
}

async function filesMatch(source, target) {
  if (target.kind !== 'file') return false
  const [sourceBytes, targetBytes] = await Promise.all([readFile(source.absolute), readFile(target.absolute)])
  return sourceBytes.equals(targetBytes) && (source.info.mode & 0o111) === (target.info.mode & 0o111)
}

async function sourceAssetInventory(skills) {
  const files = new Map()
  const directories = new Set()
  for (const { name, sourceRoot } of skills) {
    directories.add(name)
    const tree = await collectTree(path.join(sourceRoot, name), { rejectSymlinks: true })
    for (const directory of tree.directories) directories.add(`${name}/${directory}`)
    for (const [file, asset] of tree.files) {
      files.set(`${name}/${file}`, { asset, record: await assetRecord(asset) })
    }
  }
  return { files, directories }
}

async function targetAssetInventory(targetRoot) {
  const info = await inspect(targetRoot)
  if (info === null) return { files: new Map(), directories: new Set() }
  if (!info.isDirectory() || info.isSymbolicLink()) {
    throw new Error('.claude/skills must be a regular directory')
  }
  const tree = await collectTree(targetRoot)
  tree.files.delete(OWNERSHIP_MANIFEST)
  return tree
}

async function auditOwnershipManifest(repo, skills, targetRoot, manifest) {
  const issues = []
  if (!manifest.exists) {
    if (skills.length === 0) return issues
    issues.push(`${OWNERSHIP_MANIFEST_PATH}: ownership baseline is missing; run --write to claim an exact legacy mirror`)
    return issues
  }
  if (!manifest.canonical) {
    issues.push(`${OWNERSHIP_MANIFEST_PATH}: manifest bytes are not deterministic; run --write to normalize it`)
  }

  const [source, target] = await Promise.all([
    sourceAssetInventory(skills),
    targetAssetInventory(targetRoot),
  ])
  for (const [assetPath, sourceEntry] of source.files) {
    const baseline = manifest.files.get(assetPath)
    if (baseline === undefined) {
      issues.push(`${OWNERSHIP_MANIFEST_PATH}: missing managed file record for ${assetPath}`)
      continue
    }
    if (!recordsEqual(sourceEntry.record, baseline)) {
      issues.push(`${OWNERSHIP_MANIFEST_PATH}: canonical asset diverges from baseline: ${assetPath}`)
    }
    const targetAsset = target.files.get(assetPath)
    const targetRecord = await assetRecord(targetAsset)
    if (targetAsset !== undefined && !recordsEqual(targetRecord, baseline)) {
      issues.push(`${OWNERSHIP_MANIFEST_PATH}: mirrored asset diverges from baseline: ${assetPath}`)
    }
  }
  for (const assetPath of manifest.files.keys()) {
    if (!source.files.has(assetPath)) {
      if (isIgnoredCanonicalAsset(repo, assetPath)) continue
      issues.push(`${OWNERSHIP_MANIFEST_PATH}: stale managed file record: ${assetPath}`)
    }
  }
  return issues
}

async function writeOwnershipManifest(repo, skills) {
  const source = await sourceAssetInventory(skills)
  const files = new Map([...source.files].map(([assetPath, entry]) => [assetPath, entry.record]))
  const manifestPath = path.join(repo, ...OWNERSHIP_MANIFEST_PATH.split('/'))
  await atomicWriteText(manifestPath, serializeOwnershipManifest(files), 0o644)
}

async function writeLocalProvenance(repo, skills) {
  const provenancePath = localProvenancePath(repo)
  if (provenancePath === null) return
  const source = await sourceAssetInventory(skills)
  const files = new Map([...source.files].map(([assetPath, entry]) => [assetPath, entry.record]))
  await atomicWriteText(provenancePath, serializeOwnershipManifest(files), 0o600)
}

function localConflict(label) {
  return `${label}: untracked or ignored Claude skill conflicts with the canonical source; migrate or remove the local asset before syncing`
}

function divergentConflict(label) {
  return `${label}: canonical and mirrored assets do not have a safe ownership direction; preserve the mirror, migrate the intended content, then retry`
}

function trackedExtraConflict(label) {
  return `${label}: tracked Claude-only asset has no ownership baseline; migrate to ${canonicalPathForMirror(label)} or rerun with --force-migration after preserving intended content`
}

function mutationBaseline(assetPath, tracked, manifest, localProvenance) {
  return (tracked ? manifest.files : localProvenance.files).get(assetPath)
}

function hasMutationBaseline(assetPath, tracked, manifest, localProvenance) {
  return hasManifestPath(tracked ? manifest.files : localProvenance.files, assetPath)
}

function replacementDecision(sourceRecord, targetRecord, baseline, tracked) {
  if (recordsEqual(sourceRecord, targetRecord)) return 'same'
  if (baseline !== undefined) {
    const sourceMatches = recordsEqual(sourceRecord, baseline)
    const targetMatches = recordsEqual(targetRecord, baseline)
    if (!sourceMatches && targetMatches) return 'replace'
    if (sourceMatches && !targetMatches) return 'reverse'
    return 'conflict'
  }
  return 'conflict'
}

function staleRemovalDecision(targetRecord, baseline, tracked) {
  if (baseline !== undefined) return recordsEqual(targetRecord, baseline) ? 'remove' : 'conflict'
  return tracked ? 'remove' : 'preserve'
}

async function findUntrackedSkillConflicts(
  repo,
  skills,
  targetRoot,
  trackedAssets,
  manifest,
  localProvenance,
  forceMigration,
) {
  const conflicts = []
  for (const { name, sourceRoot } of skills) {
    const sourceSkill = path.join(sourceRoot, name)
    const targetSkill = path.join(targetRoot, name)
    const targetLabel = relative(repo, targetSkill)
    const targetInfo = await inspect(targetSkill)
    if (targetInfo === null) continue
    if (!targetInfo.isDirectory() || targetInfo.isSymbolicLink()) {
      const tracked = trackedAssets.has(targetLabel)
      if (hasMutationBaseline(name, tracked, manifest, localProvenance)) {
        conflicts.push(divergentConflict(targetLabel))
      } else if (!tracked) {
        conflicts.push(localConflict(targetLabel))
      }
      continue
    }

    const [sourceTree, targetTree] = await Promise.all([
      collectTree(sourceSkill, { rejectSymlinks: true }),
      collectTree(targetSkill),
    ])
    for (const [file, target] of targetTree.files) {
      const label = relative(repo, path.join(targetSkill, file))
      const source = sourceTree.files.get(file)
      const assetPath = `${name}/${file}`
      const tracked = trackedAssets.has(label)
      const baseline = mutationBaseline(assetPath, tracked, manifest, localProvenance)
      const targetRecord = await assetRecord(target)
      if (source !== undefined) {
        const sourceRecord = await assetRecord(source)
        if (replacementDecision(sourceRecord, targetRecord, baseline, tracked) === 'conflict') {
          conflicts.push(baseline === undefined ? localConflict(label) : divergentConflict(label))
        }
      } else if (sourceTree.directories.has(file)) {
        if (baseline === undefined && tracked && !forceMigration) {
          conflicts.push(trackedExtraConflict(label))
          continue
        }
        const decision = staleRemovalDecision(targetRecord, baseline, tracked)
        if (decision !== 'remove') {
          conflicts.push(decision === 'preserve' ? localConflict(label) : divergentConflict(label))
        }
      } else if (baseline !== undefined && staleRemovalDecision(targetRecord, baseline, false) === 'conflict') {
        conflicts.push(divergentConflict(label))
      }
    }

    for (const file of sourceTree.files.keys()) {
      if (!targetTree.directories.has(file)) continue
      const label = relative(repo, path.join(targetSkill, file))
      const prefix = `${file}/`
      const descendants = [...targetTree.files.keys()].filter(target => target.startsWith(prefix))
      const fullyOwned =
        descendants.length > 0 &&
        (
          await Promise.all(
            descendants.map(async target => {
              const descendantLabel = relative(repo, path.join(targetSkill, target))
              const tracked = trackedAssets.has(descendantLabel)
              const baseline = mutationBaseline(`${name}/${target}`, tracked, manifest, localProvenance)
              const targetRecord = await assetRecord(targetTree.files.get(target))
              return staleRemovalDecision(targetRecord, baseline, tracked) === 'remove'
            }),
          )
        ).every(Boolean)
      if (!fullyOwned) conflicts.push(divergentConflict(label))
    }
  }
  return [...new Set(conflicts)].sort()
}

async function findStaleManifestConflicts(
  repo,
  skills,
  targetRoot,
  trackedAssets,
  manifest,
  localProvenance,
) {
  const [source, target] = await Promise.all([
    sourceAssetInventory(skills),
    targetAssetInventory(targetRoot),
  ])
  const conflicts = []
  const candidates = new Set([...manifest.files.keys(), ...localProvenance.files.keys()])
  for (const assetPath of candidates) {
    if (source.files.has(assetPath)) continue
    if (isIgnoredCanonicalAsset(repo, assetPath)) continue
    const targetAsset = target.files.get(assetPath)
    if (targetAsset !== undefined) {
      const label = relative(repo, path.join(targetRoot, ...assetPath.split('/')))
      const baseline = mutationBaseline(assetPath, trackedAssets.has(label), manifest, localProvenance)
      if (baseline !== undefined && !recordsEqual(await assetRecord(targetAsset), baseline)) {
        conflicts.push(divergentConflict(label))
      }
    }
  }
  return conflicts
}

async function removeStaleManifestAssets(repo, skills, targetRoot, trackedAssets, manifest, localProvenance) {
  const [source, target] = await Promise.all([
    sourceAssetInventory(skills),
    targetAssetInventory(targetRoot),
  ])
  const removed = []
  const candidates = new Set([...manifest.files.keys(), ...localProvenance.files.keys()])
  for (const assetPath of candidates) {
    if (source.files.has(assetPath)) continue
    if (isIgnoredCanonicalAsset(repo, assetPath)) continue
    const targetAsset = target.files.get(assetPath)
    if (targetAsset !== undefined) {
      const label = relative(repo, path.join(targetRoot, ...assetPath.split('/')))
      const baseline = mutationBaseline(assetPath, trackedAssets.has(label), manifest, localProvenance)
      if (baseline !== undefined && recordsEqual(await assetRecord(targetAsset), baseline)) {
        await unlink(targetAsset.absolute)
        removed.push(targetAsset.absolute)
      }
    }
  }

  const parents = new Set()
  for (const removedAsset of removed) {
    let parent = path.dirname(removedAsset)
    while (parent.startsWith(`${targetRoot}${path.sep}`)) {
      parents.add(parent)
      parent = path.dirname(parent)
    }
  }
  for (const parent of [...parents].sort((left, right) => right.length - left.length)) {
    try {
      await rmdir(parent)
    } catch (error) {
      if (error?.code !== 'ENOENT' && error?.code !== 'ENOTEMPTY' && error?.code !== 'EEXIST') throw error
    }
  }
}

async function syncSkill(repo, name, sourceRoot, targetRoot, trackedAssets, manifest, localProvenance) {
  const sourceSkill = path.join(sourceRoot, name)
  const targetSkill = path.join(targetRoot, name)
  const targetLabel = relative(repo, targetSkill)
  const targetInfo = await inspect(targetSkill)
  if (targetInfo !== null && (!targetInfo.isDirectory() || targetInfo.isSymbolicLink())) {
    const tracked = trackedAssets.has(targetLabel)
    if (hasMutationBaseline(name, tracked, manifest, localProvenance)) {
      throw new Error(divergentConflict(targetLabel))
    }
    if (!tracked) throw new Error(localConflict(targetLabel))
    await unlink(targetSkill)
  }
  await mkdir(targetSkill, { recursive: true })

  const sourceTree = await collectTree(sourceSkill, { rejectSymlinks: true })
  const targetTree = await collectTree(targetSkill)

  for (const [file, target] of targetTree.files) {
    const label = relative(repo, path.join(targetSkill, file))
    const source = sourceTree.files.get(file)
    const assetPath = `${name}/${file}`
    const tracked = trackedAssets.has(label)
    const baseline = mutationBaseline(assetPath, tracked, manifest, localProvenance)
    const targetRecord = await assetRecord(target)
    let remove = false
    if (source !== undefined) {
      const sourceRecord = await assetRecord(source)
      const decision = replacementDecision(sourceRecord, targetRecord, baseline, tracked)
      if (decision === 'reverse') {
        await atomicCopy(target.absolute, source.absolute, target.info.mode)
      }
      remove = decision === 'replace'
    } else {
      if (baseline === undefined) {
        await atomicCopy(target.absolute, path.join(sourceSkill, file), target.info.mode)
      } else {
        remove = staleRemovalDecision(targetRecord, baseline, tracked) === 'remove'
      }
    }
    if (remove) {
      await unlink(target.absolute)
    }
  }

  for (const [file, source] of sourceTree.files) {
    const destination = path.join(targetSkill, file)
    const destinationInfo = await inspect(destination)
    if (destinationInfo?.isDirectory() && !destinationInfo.isSymbolicLink()) {
      await rmdir(destination)
    } else if (destinationInfo?.isSymbolicLink()) {
      throw new Error(localConflict(relative(repo, destination)))
    } else if (destinationInfo?.isFile()) {
      const target = { absolute: destination, info: destinationInfo, kind: 'file' }
      if (await filesMatch(source, target)) continue
    }
    await atomicCopy(source.absolute, destination, source.info.mode)
  }

  const currentTree = await collectTree(targetSkill)
  const extraDirectories = [...currentTree.directories]
    .filter(directory => {
      const label = relative(repo, path.join(targetSkill, directory))
      const tracked = hasTrackedPath(trackedAssets, label)
      return (
        !sourceTree.directories.has(directory) &&
        (tracked ||
          hasManifestPath(
            tracked ? manifest.files : localProvenance.files,
            `${name}/${directory}`,
          ))
      )
    })
    .sort((left, right) => right.split('/').length - left.split('/').length || right.localeCompare(left))
  for (const directory of extraDirectories) {
    try {
      await rmdir(path.join(targetSkill, directory))
    } catch (error) {
      if (error?.code !== 'ENOENT' && error?.code !== 'ENOTEMPTY' && error?.code !== 'EEXIST') throw error
    }
  }
}

async function removeTrackedMirrorOnlyAssets(repo, canonicalNames, targetRoot, trackedAssets) {
  const assets = await trackedMirrorOnlyAssets(repo, canonicalNames, trackedAssets)
  for (const asset of assets) {
    const info = await inspect(asset.absolute)
    if (info !== null && (!info.isDirectory() || info.isSymbolicLink())) await unlink(asset.absolute)
  }

  const parents = new Set()
  for (const asset of assets) {
    let parent = path.dirname(asset.absolute)
    while (parent.startsWith(`${targetRoot}${path.sep}`)) {
      parents.add(parent)
      parent = path.dirname(parent)
    }
  }
  for (const parent of [...parents].sort((left, right) => right.length - left.length)) {
    try {
      await rmdir(parent)
    } catch (error) {
      if (error?.code !== 'ENOENT' && error?.code !== 'ENOTEMPTY' && error?.code !== 'EEXIST') throw error
    }
  }
}

async function write(repo, { forceMigration = false } = {}) {
  const { sharedSkillRoot, sharedInstructions } = await assertSafeRepoLayout(repo)
  const externalGeneratedInstructions =
    !sharedInstructions && (await usesExternalGeneratedInstructions(repo))
  // Validate both managed and local skill inputs before the first write so an
  // invalid skill cannot leave a partially migrated root contract behind.
  if (!sharedSkillRoot) {
    await discoverSkills(repo)
    await validatePairedMirrorSkills(repo)
    await planIgnoredSkillSync(repo)
  }
  if (!sharedInstructions && !externalGeneratedInstructions) {
    await synchronizeRootInstructions(repo)
  }
  const agents = path.join(repo, 'AGENTS.md')
  const agentsInfo = await inspect(agents)
  if (agentsInfo !== null && !sharedInstructions && (!agentsInfo.isFile() || agentsInfo.isSymbolicLink())) {
    throw new Error('AGENTS.md must be a regular file')
  }
  const agentsContents = agentsInfo === null ? '' : await readFile(agents, 'utf8')
  const routingIssues = await auditRuleRouting(repo, agentsContents)
  if (routingIssues.length > 0) {
    throw new Error(`rule routing parity failed:\n${routingIssues.map(issue => `- ${issue}`).join('\n')}`)
  }

  if (sharedSkillRoot) {
    const result = await audit(repo)
    if (result.issues.length > 0) {
      throw new Error(`synchronization did not converge:\n${result.issues.map(issue => `- ${issue}`).join('\n')}`)
    }
    return result.skills.length
  }

  await mkdir(path.join(repo, '.agents', 'skills'), { recursive: true })
  await mkdir(path.join(repo, '.claude', 'skills'), { recursive: true })
  await synchronizeIgnoredSkills(repo)

  const skills = await discoverSkills(repo)
  const trackedAssets = trackedSkillAssets(repo)
  const targetRoot = path.join(repo, '.claude', 'skills')
  const manifest = await loadOwnershipManifest(repo)
  const localProvenance = await loadLocalProvenance(repo)
  const canonicalNames = new Set(skills.map(skill => skill.name))
  const mirrorOnlyAssets = await trackedMirrorOnlyAssets(repo, canonicalNames, trackedAssets)
  if (mirrorOnlyAssets.length > 0 && !forceMigration) {
    throw new Error(
      `tracked Claude-only skill requires explicit migration; preserved:\n${mirrorOnlyAssets.map(asset => `- ${asset.relative} -> ${canonicalPathForMirror(asset.relative)}`).join('\n')}\nRerun with --force-migration only after preserving any intended content.`,
    )
  }
  const localConflicts = [
    ...(await findUntrackedSkillConflicts(
      repo,
      skills,
      targetRoot,
      trackedAssets,
      manifest,
      localProvenance,
      forceMigration,
    )),
    ...(await findStaleManifestConflicts(
      repo,
      skills,
      targetRoot,
      trackedAssets,
      manifest,
      localProvenance,
    )),
  ]
  if (localConflicts.length > 0) {
    throw new Error(`local Claude skill migration required:\n${localConflicts.map(issue => `- ${issue}`).join('\n')}`)
  }
  const claude = path.join(repo, 'CLAUDE.md')
  if (agentsInfo !== null && (await inspect(claude)) === null) {
    await atomicWriteText(claude, CLAUDE_IMPORT, 0o644)
  }
  await mkdir(targetRoot, { recursive: true })
  for (const skill of skills) {
    await syncSkill(
      repo,
      skill.name,
      skill.sourceRoot,
      targetRoot,
      trackedAssets,
      manifest,
      localProvenance,
    )
  }
  await removeStaleManifestAssets(
    repo,
    skills,
    targetRoot,
    trackedAssets,
    manifest,
    localProvenance,
  )
  if (forceMigration) {
    await removeTrackedMirrorOnlyAssets(repo, canonicalNames, targetRoot, trackedAssets)
  }
  await writeOwnershipManifest(repo, skills)
  await writeLocalProvenance(repo, skills)

  const result = await audit(repo)
  if (result.issues.length > 0) {
    throw new Error(`synchronization did not converge:\n${result.issues.map(issue => `- ${issue}`).join('\n')}`)
  }
  return skills.length
}

async function install(repo) {
  await assertSafeRepoLayout(repo, { includeInstallerDestination: true })
  const source = fileURLToPath(import.meta.url)
  const destination = path.join(repo, INSTALLED_PATH)
  const repoInfo = await inspect(repo)
  if (repoInfo === null || !repoInfo.isDirectory()) throw new Error(`repository path does not exist: ${repo}`)

  if (path.resolve(source) !== path.resolve(destination)) {
    await atomicCopy(source, destination, 0o755)
  } else {
    await chmod(destination, 0o755)
  }
  return destination
}

function shellQuote(value) {
  if (/^[A-Za-z0-9_./:=+-]+$/.test(value)) return value
  return `'${value.replaceAll("'", "'\\''")}'`
}

function modeCommand(mode, repo) {
  return [
    shellQuote(process.execPath),
    shellQuote(fileURLToPath(import.meta.url)),
    `--${mode}`,
    '--repo',
    shellQuote(repo),
  ].join(' ')
}

async function main() {
  let options
  try {
    options = parseArgs(process.argv.slice(2))
  } catch (error) {
    if (!(error instanceof UsageError)) throw error
    console.error(`Error: ${error.message}\n\n${usage()}`)
    process.exitCode = 2
    return
  }

  if (options.help) {
    console.log(usage())
    return
  }

  if (options.mode === 'install') {
    const count = await write(options.repo, { forceMigration: options.forceMigration })
    const destination = await install(options.repo)
    console.log(`Installed ${relative(options.repo, destination)}`)
    console.log(`Synchronized CLAUDE.md and ${count} skill${count === 1 ? '' : 's'}.`)
    console.log(`Check: node ${INSTALLED_PATH.split(path.sep).join('/')} --check`)
    return
  }

  if (options.mode === 'write') {
    const count = await write(options.repo, { forceMigration: options.forceMigration })
    console.log(`Synchronized CLAUDE.md and ${count} skill${count === 1 ? '' : 's'}.`)
    return
  }

  const { issues, skills } = await audit(options.repo)
  if (issues.length === 0) {
    console.log(`Agent assets are synchronized (${skills.length} skill${skills.length === 1 ? '' : 's'}).`)
    return
  }

  console.error('Agent asset drift detected:')
  for (const issue of issues) console.error(`- ${issue}`)
  if (issues.some(issue => issue.startsWith('AGENTS.md '))) {
    console.error(`Verify after correcting AGENTS.md: ${modeCommand('check', options.repo)}`)
  } else {
    console.error(`Recovery: ${modeCommand('write', options.repo)}`)
  }
  process.exitCode = 1
}

main().catch(error => {
  console.error(`Error: ${error.message}`)
  process.exitCode = 1
})
