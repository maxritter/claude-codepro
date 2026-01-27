"use strict";var _t=Object.create;var k=Object.defineProperty;var Et=Object.getOwnPropertyDescriptor;var gt=Object.getOwnPropertyNames;var Tt=Object.getPrototypeOf,ft=Object.prototype.hasOwnProperty;var St=(n,e)=>{for(var t in e)k(n,t,{get:e[t],enumerable:!0})},re=(n,e,t,s)=>{if(e&&typeof e=="object"||typeof e=="function")for(let r of gt(e))!ft.call(n,r)&&r!==t&&k(n,r,{get:()=>e[r],enumerable:!(s=Et(e,r))||s.enumerable});return n};var L=(n,e,t)=>(t=n!=null?_t(Tt(n)):{},re(e||!n||!n.__esModule?k(t,"default",{value:n,enumerable:!0}):t,n)),bt=n=>re(k({},"__esModule",{value:!0}),n);var kt={};St(kt,{generateContext:()=>se});module.exports=bt(kt);var ut=L(require("path"),1),mt=require("os"),lt=require("fs");var _e=require("bun:sqlite");var b=require("path"),ce=require("os"),w=require("fs");var pe=require("url");var R=require("fs"),$=require("path"),ie=require("os");var ne="bugfix,feature,refactor,discovery,decision,change",oe="how-it-works,why-it-exists,what-changed,problem-solution,gotcha,pattern,trade-off";var A=class{static DEFAULTS={CLAUDE_MEM_MODEL:"haiku",CLAUDE_MEM_CONTEXT_OBSERVATIONS:"50",CLAUDE_MEM_WORKER_PORT:"37777",CLAUDE_MEM_WORKER_HOST:"127.0.0.1",CLAUDE_MEM_WORKER_BIND:"127.0.0.1",CLAUDE_MEM_SKIP_TOOLS:"ListMcpResourcesTool,SlashCommand,Skill,TodoWrite,AskUserQuestion",CLAUDE_MEM_PROVIDER:"claude",CLAUDE_MEM_GEMINI_API_KEY:"",CLAUDE_MEM_GEMINI_MODEL:"gemini-2.5-flash-lite",CLAUDE_MEM_GEMINI_RATE_LIMITING_ENABLED:!0,CLAUDE_MEM_OPENROUTER_API_KEY:"",CLAUDE_MEM_OPENROUTER_MODEL:"xiaomi/mimo-v2-flash:free",CLAUDE_MEM_OPENROUTER_SITE_URL:"",CLAUDE_MEM_OPENROUTER_APP_NAME:"claude-mem",CLAUDE_MEM_OPENROUTER_MAX_CONTEXT_MESSAGES:"20",CLAUDE_MEM_OPENROUTER_MAX_TOKENS:"100000",CLAUDE_MEM_MISTRAL_API_KEY:"",CLAUDE_MEM_MISTRAL_MODEL:"mistral-small-latest",CLAUDE_MEM_OPENAI_API_KEY:"",CLAUDE_MEM_OPENAI_MODEL:"gpt-4o-mini",CLAUDE_MEM_OPENAI_BASE_URL:"",CLAUDE_MEM_DATA_DIR:(0,$.join)((0,ie.homedir)(),".claude-mem"),CLAUDE_MEM_LOG_LEVEL:"INFO",CLAUDE_MEM_PYTHON_VERSION:"3.12",CLAUDE_CODE_PATH:"",CLAUDE_MEM_MODE:"code",CLAUDE_MEM_CONTEXT_SHOW_READ_TOKENS:!1,CLAUDE_MEM_CONTEXT_SHOW_WORK_TOKENS:!1,CLAUDE_MEM_CONTEXT_SHOW_SAVINGS_AMOUNT:!1,CLAUDE_MEM_CONTEXT_SHOW_SAVINGS_PERCENT:!1,CLAUDE_MEM_CONTEXT_OBSERVATION_TYPES:ne,CLAUDE_MEM_CONTEXT_OBSERVATION_CONCEPTS:oe,CLAUDE_MEM_CONTEXT_FULL_COUNT:"10",CLAUDE_MEM_CONTEXT_FULL_FIELD:"facts",CLAUDE_MEM_CONTEXT_SESSION_COUNT:"10",CLAUDE_MEM_CONTEXT_SHOW_LAST_SUMMARY:!0,CLAUDE_MEM_CONTEXT_SHOW_LAST_MESSAGE:!0,CLAUDE_MEM_FOLDER_CLAUDEMD_ENABLED:!1,CLAUDE_MEM_FOLDER_MD_EXCLUDE:"[]",CLAUDE_MEM_CHROMA_ENABLED:!0,CLAUDE_MEM_VECTOR_DB:"chroma",CLAUDE_MEM_EMBEDDING_MODEL:"Xenova/all-MiniLM-L6-v2",CLAUDE_MEM_EXCLUDE_PROJECTS:"[]",CLAUDE_MEM_REMOTE_MODE:!1,CLAUDE_MEM_REMOTE_URL:"",CLAUDE_MEM_REMOTE_TOKEN:"",CLAUDE_MEM_REMOTE_VERIFY_SSL:!0,CLAUDE_MEM_REMOTE_TIMEOUT_MS:"30000",CLAUDE_MEM_RETENTION_ENABLED:!0,CLAUDE_MEM_RETENTION_MAX_AGE_DAYS:"31",CLAUDE_MEM_RETENTION_MAX_COUNT:"1000",CLAUDE_MEM_RETENTION_EXCLUDE_TYPES:'["summary"]',CLAUDE_MEM_RETENTION_SOFT_DELETE:!1,CLAUDE_MEM_BATCH_SIZE:"5"};static getAllDefaults(){return{...this.DEFAULTS}}static get(e){return this.DEFAULTS[e]}static getInt(e){let t=this.get(e);return parseInt(t,10)}static getBool(e){return this.get(e)==="true"}static loadFromFile(e){try{if(!(0,R.existsSync)(e)){let a=this.getAllDefaults();try{let p=(0,$.dirname)(e);(0,R.existsSync)(p)||(0,R.mkdirSync)(p,{recursive:!0}),(0,R.writeFileSync)(e,JSON.stringify(a,null,2),"utf-8"),console.log("[SETTINGS] Created settings file with defaults:",e)}catch(p){console.warn("[SETTINGS] Failed to create settings file, using in-memory defaults:",e,p)}return a}let t=(0,R.readFileSync)(e,"utf-8"),s=JSON.parse(t),r=s;if(s.env&&typeof s.env=="object"){r=s.env;try{(0,R.writeFileSync)(e,JSON.stringify(r,null,2),"utf-8"),console.log("[SETTINGS] Migrated settings file from nested to flat schema:",e)}catch(a){console.warn("[SETTINGS] Failed to auto-migrate settings file:",e,a)}}let o=["CLAUDE_MEM_GEMINI_RATE_LIMITING_ENABLED","CLAUDE_MEM_CONTEXT_SHOW_READ_TOKENS","CLAUDE_MEM_CONTEXT_SHOW_WORK_TOKENS","CLAUDE_MEM_CONTEXT_SHOW_SAVINGS_AMOUNT","CLAUDE_MEM_CONTEXT_SHOW_SAVINGS_PERCENT","CLAUDE_MEM_CONTEXT_SHOW_LAST_SUMMARY","CLAUDE_MEM_CONTEXT_SHOW_LAST_MESSAGE","CLAUDE_MEM_FOLDER_CLAUDEMD_ENABLED","CLAUDE_MEM_CHROMA_ENABLED","CLAUDE_MEM_REMOTE_MODE","CLAUDE_MEM_REMOTE_VERIFY_SSL","CLAUDE_MEM_RETENTION_ENABLED","CLAUDE_MEM_RETENTION_SOFT_DELETE"],i={...this.DEFAULTS},d=!1;for(let a of Object.keys(this.DEFAULTS))if(r[a]!==void 0)if(o.includes(a)){let p=r[a];typeof p=="string"?(i[a]=p==="true",d=!0):i[a]=p}else i[a]=r[a];if(d)try{(0,R.writeFileSync)(e,JSON.stringify(i,null,2),"utf-8"),console.log("[SETTINGS] Migrated boolean settings from strings to actual booleans:",e)}catch(a){console.warn("[SETTINGS] Failed to auto-migrate boolean settings:",e,a)}return i}catch(t){return console.warn("[SETTINGS] Failed to load settings, using defaults:",e,t),this.getAllDefaults()}}};var N=require("fs"),y=require("path"),de=require("os"),G=(o=>(o[o.DEBUG=0]="DEBUG",o[o.INFO=1]="INFO",o[o.WARN=2]="WARN",o[o.ERROR=3]="ERROR",o[o.SILENT=4]="SILENT",o))(G||{}),ae=(0,y.join)((0,de.homedir)(),".claude-mem"),Y=class{level=null;useColor;logFilePath=null;logFileInitialized=!1;constructor(){this.useColor=process.stdout.isTTY??!1}ensureLogFileInitialized(){if(!this.logFileInitialized){this.logFileInitialized=!0;try{let e=(0,y.join)(ae,"logs");(0,N.existsSync)(e)||(0,N.mkdirSync)(e,{recursive:!0});let t=new Date().toISOString().split("T")[0];this.logFilePath=(0,y.join)(e,`claude-mem-${t}.log`)}catch(e){console.error("[LOGGER] Failed to initialize log file:",e),this.logFilePath=null}}}getLevel(){if(this.level===null)try{let e=(0,y.join)(ae,"settings.json");if((0,N.existsSync)(e)){let t=(0,N.readFileSync)(e,"utf-8"),r=(JSON.parse(t).CLAUDE_MEM_LOG_LEVEL||"INFO").toUpperCase();this.level=G[r]??1}else this.level=1}catch{this.level=1}return this.level}correlationId(e,t){return`obs-${e}-${t}`}sessionId(e){return`session-${e}`}formatData(e){if(e==null)return"";if(typeof e=="string")return e;if(typeof e=="number"||typeof e=="boolean")return e.toString();if(typeof e=="object"){if(e instanceof Error)return this.getLevel()===0?`${e.message}
${e.stack}`:e.message;if(Array.isArray(e))return`[${e.length} items]`;let t=Object.keys(e);return t.length===0?"{}":t.length<=3?JSON.stringify(e):`{${t.length} keys: ${t.slice(0,3).join(", ")}...}`}return String(e)}formatTool(e,t){if(!t)return e;let s=t;if(typeof t=="string")try{s=JSON.parse(t)}catch{s=t}if(e==="Bash"&&s.command)return`${e}(${s.command})`;if(s.file_path)return`${e}(${s.file_path})`;if(s.notebook_path)return`${e}(${s.notebook_path})`;if(e==="Glob"&&s.pattern)return`${e}(${s.pattern})`;if(e==="Grep"&&s.pattern)return`${e}(${s.pattern})`;if(s.url)return`${e}(${s.url})`;if(s.query)return`${e}(${s.query})`;if(e==="Task"){if(s.subagent_type)return`${e}(${s.subagent_type})`;if(s.description)return`${e}(${s.description})`}return e==="Skill"&&s.skill?`${e}(${s.skill})`:e==="LSP"&&s.operation?`${e}(${s.operation})`:e}formatTimestamp(e){let t=e.getFullYear(),s=String(e.getMonth()+1).padStart(2,"0"),r=String(e.getDate()).padStart(2,"0"),o=String(e.getHours()).padStart(2,"0"),i=String(e.getMinutes()).padStart(2,"0"),d=String(e.getSeconds()).padStart(2,"0"),a=String(e.getMilliseconds()).padStart(3,"0");return`${t}-${s}-${r} ${o}:${i}:${d}.${a}`}log(e,t,s,r,o){if(e<this.getLevel())return;this.ensureLogFileInitialized();let i=this.formatTimestamp(new Date),d=G[e].padEnd(5),a=t.padEnd(6),p="";r?.correlationId?p=`[${r.correlationId}] `:r?.sessionId&&(p=`[session-${r.sessionId}] `);let m="";o!=null&&(o instanceof Error?m=this.getLevel()===0?`
${o.message}
${o.stack}`:` ${o.message}`:this.getLevel()===0&&typeof o=="object"?m=`
`+JSON.stringify(o,null,2):m=" "+this.formatData(o));let l="";if(r){let{sessionId:E,memorySessionId:T,correlationId:h,..._}=r;Object.keys(_).length>0&&(l=` {${Object.entries(_).map(([f,C])=>`${f}=${C}`).join(", ")}}`)}let g=`[${i}] [${d}] [${a}] ${p}${s}${l}${m}`;if(this.logFilePath)try{(0,N.appendFileSync)(this.logFilePath,g+`
`,"utf8")}catch(E){process.stderr.write(`[LOGGER] Failed to write to log file: ${E}
`)}else process.stderr.write(g+`
`)}debug(e,t,s,r){this.log(0,e,t,s,r)}info(e,t,s,r){this.log(1,e,t,s,r)}warn(e,t,s,r){this.log(2,e,t,s,r)}error(e,t,s,r){this.log(3,e,t,s,r)}dataIn(e,t,s,r){this.info(e,`\u2192 ${t}`,s,r)}dataOut(e,t,s,r){this.info(e,`\u2190 ${t}`,s,r)}success(e,t,s,r){this.info(e,`\u2713 ${t}`,s,r)}failure(e,t,s,r){this.error(e,`\u2717 ${t}`,s,r)}timing(e,t,s,r){this.info(e,`\u23F1 ${t}`,r,{duration:`${s}ms`})}happyPathError(e,t,s,r,o=""){let p=((new Error().stack||"").split(`
`)[2]||"").match(/at\s+(?:.*\s+)?\(?([^:]+):(\d+):(\d+)\)?/),m=p?`${p[1].split("/").pop()}:${p[2]}`:"unknown",l={...s,location:m};return this.warn(e,`[HAPPY-PATH] ${t}`,l,r),o}},u=new Y;var Rt={};function ht(){return typeof __dirname<"u"?__dirname:(0,b.dirname)((0,pe.fileURLToPath)(Rt.url))}var Ot=ht(),M=A.get("CLAUDE_MEM_DATA_DIR"),D=process.env.CLAUDE_CONFIG_DIR||(0,b.join)((0,ce.homedir)(),".claude"),Wt=(0,b.join)(M,"archives"),Gt=(0,b.join)(M,"logs"),Yt=(0,b.join)(M,"trash"),Vt=(0,b.join)(M,"backups"),Kt=(0,b.join)(M,"modes"),qt=(0,b.join)(M,"settings.json"),ue=(0,b.join)(M,"claude-mem.db"),Jt=(0,b.join)(M,"vector-db"),zt=(0,b.join)(D,"settings.json"),Qt=(0,b.join)(D,"commands"),Zt=(0,b.join)(D,"CLAUDE.md"),es=(0,b.join)(D,".credentials.json"),Ct=(0,b.join)(D,"plugins"),ts=(0,b.join)(Ct,"marketplaces","customable");function me(n){(0,w.mkdirSync)(n,{recursive:!0})}function le(){return(0,b.join)(Ot,"..")}var F=class{db;constructor(e=ue){e!==":memory:"&&me(M),this.db=new _e.Database(e),this.db.run("PRAGMA journal_mode = WAL"),this.db.run("PRAGMA synchronous = NORMAL"),this.db.run("PRAGMA foreign_keys = ON"),this.initializeSchema(),this.ensureWorkerPortColumn(),this.ensurePromptTrackingColumns(),this.removeSessionSummariesUniqueConstraint(),this.addObservationHierarchicalFields(),this.makeObservationsTextNullable(),this.createUserPromptsTable(),this.ensureDiscoveryTokensColumn(),this.createPendingMessagesTable(),this.renameSessionIdColumns(),this.repairSessionIdColumnRename(),this.addFailedAtEpochColumn()}initializeSchema(){this.db.run(`
      CREATE TABLE IF NOT EXISTS schema_versions (
        id INTEGER PRIMARY KEY,
        version INTEGER UNIQUE NOT NULL,
        applied_at TEXT NOT NULL
      )
    `);let e=this.db.prepare("SELECT version FROM schema_versions ORDER BY version").all();(e.length>0?Math.max(...e.map(s=>s.version)):0)===0&&(u.info("DB","Initializing fresh database with migration004"),this.db.run(`
        CREATE TABLE IF NOT EXISTS sdk_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          content_session_id TEXT UNIQUE NOT NULL,
          memory_session_id TEXT UNIQUE,
          project TEXT NOT NULL,
          user_prompt TEXT,
          started_at TEXT NOT NULL,
          started_at_epoch INTEGER NOT NULL,
          completed_at TEXT,
          completed_at_epoch INTEGER,
          status TEXT CHECK(status IN ('active', 'completed', 'failed')) NOT NULL DEFAULT 'active'
        );

        CREATE INDEX IF NOT EXISTS idx_sdk_sessions_claude_id ON sdk_sessions(content_session_id);
        CREATE INDEX IF NOT EXISTS idx_sdk_sessions_sdk_id ON sdk_sessions(memory_session_id);
        CREATE INDEX IF NOT EXISTS idx_sdk_sessions_project ON sdk_sessions(project);
        CREATE INDEX IF NOT EXISTS idx_sdk_sessions_status ON sdk_sessions(status);
        CREATE INDEX IF NOT EXISTS idx_sdk_sessions_started ON sdk_sessions(started_at_epoch DESC);

        CREATE TABLE IF NOT EXISTS observations (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          memory_session_id TEXT NOT NULL,
          project TEXT NOT NULL,
          text TEXT NOT NULL,
          type TEXT NOT NULL CHECK(type IN ('decision', 'bugfix', 'feature', 'refactor', 'discovery')),
          created_at TEXT NOT NULL,
          created_at_epoch INTEGER NOT NULL,
          FOREIGN KEY(memory_session_id) REFERENCES sdk_sessions(memory_session_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_observations_sdk_session ON observations(memory_session_id);
        CREATE INDEX IF NOT EXISTS idx_observations_project ON observations(project);
        CREATE INDEX IF NOT EXISTS idx_observations_type ON observations(type);
        CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at_epoch DESC);

        CREATE TABLE IF NOT EXISTS session_summaries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          memory_session_id TEXT UNIQUE NOT NULL,
          project TEXT NOT NULL,
          request TEXT,
          investigated TEXT,
          learned TEXT,
          completed TEXT,
          next_steps TEXT,
          files_read TEXT,
          files_edited TEXT,
          notes TEXT,
          created_at TEXT NOT NULL,
          created_at_epoch INTEGER NOT NULL,
          FOREIGN KEY(memory_session_id) REFERENCES sdk_sessions(memory_session_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_session_summaries_sdk_session ON session_summaries(memory_session_id);
        CREATE INDEX IF NOT EXISTS idx_session_summaries_project ON session_summaries(project);
        CREATE INDEX IF NOT EXISTS idx_session_summaries_created ON session_summaries(created_at_epoch DESC);
      `),this.db.prepare("INSERT INTO schema_versions (version, applied_at) VALUES (?, ?)").run(4,new Date().toISOString()),u.info("DB","Migration004 applied successfully"))}ensureWorkerPortColumn(){if(this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(5))return;this.db.query("PRAGMA table_info(sdk_sessions)").all().some(r=>r.name==="worker_port")||(this.db.run("ALTER TABLE sdk_sessions ADD COLUMN worker_port INTEGER"),u.debug("DB","Added worker_port column to sdk_sessions table")),this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(5,new Date().toISOString())}ensurePromptTrackingColumns(){if(this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(6))return;this.db.query("PRAGMA table_info(sdk_sessions)").all().some(a=>a.name==="prompt_counter")||(this.db.run("ALTER TABLE sdk_sessions ADD COLUMN prompt_counter INTEGER DEFAULT 0"),u.debug("DB","Added prompt_counter column to sdk_sessions table")),this.db.query("PRAGMA table_info(observations)").all().some(a=>a.name==="prompt_number")||(this.db.run("ALTER TABLE observations ADD COLUMN prompt_number INTEGER"),u.debug("DB","Added prompt_number column to observations table")),this.db.query("PRAGMA table_info(session_summaries)").all().some(a=>a.name==="prompt_number")||(this.db.run("ALTER TABLE session_summaries ADD COLUMN prompt_number INTEGER"),u.debug("DB","Added prompt_number column to session_summaries table")),this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(6,new Date().toISOString())}removeSessionSummariesUniqueConstraint(){if(this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(7))return;if(!this.db.query("PRAGMA index_list(session_summaries)").all().some(r=>r.unique===1)){this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(7,new Date().toISOString());return}u.debug("DB","Removing UNIQUE constraint from session_summaries.memory_session_id"),this.db.run("BEGIN TRANSACTION"),this.db.run(`
      CREATE TABLE session_summaries_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_session_id TEXT NOT NULL,
        project TEXT NOT NULL,
        request TEXT,
        investigated TEXT,
        learned TEXT,
        completed TEXT,
        next_steps TEXT,
        files_read TEXT,
        files_edited TEXT,
        notes TEXT,
        prompt_number INTEGER,
        created_at TEXT NOT NULL,
        created_at_epoch INTEGER NOT NULL,
        FOREIGN KEY(memory_session_id) REFERENCES sdk_sessions(memory_session_id) ON DELETE CASCADE
      )
    `),this.db.run(`
      INSERT INTO session_summaries_new
      SELECT id, memory_session_id, project, request, investigated, learned,
             completed, next_steps, files_read, files_edited, notes,
             prompt_number, created_at, created_at_epoch
      FROM session_summaries
    `),this.db.run("DROP TABLE session_summaries"),this.db.run("ALTER TABLE session_summaries_new RENAME TO session_summaries"),this.db.run(`
      CREATE INDEX idx_session_summaries_sdk_session ON session_summaries(memory_session_id);
      CREATE INDEX idx_session_summaries_project ON session_summaries(project);
      CREATE INDEX idx_session_summaries_created ON session_summaries(created_at_epoch DESC);
    `),this.db.run("COMMIT"),this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(7,new Date().toISOString()),u.debug("DB","Successfully removed UNIQUE constraint from session_summaries.memory_session_id")}addObservationHierarchicalFields(){if(this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(8))return;if(this.db.query("PRAGMA table_info(observations)").all().some(r=>r.name==="title")){this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(8,new Date().toISOString());return}u.debug("DB","Adding hierarchical fields to observations table"),this.db.run(`
      ALTER TABLE observations ADD COLUMN title TEXT;
      ALTER TABLE observations ADD COLUMN subtitle TEXT;
      ALTER TABLE observations ADD COLUMN facts TEXT;
      ALTER TABLE observations ADD COLUMN narrative TEXT;
      ALTER TABLE observations ADD COLUMN concepts TEXT;
      ALTER TABLE observations ADD COLUMN files_read TEXT;
      ALTER TABLE observations ADD COLUMN files_modified TEXT;
    `),this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(8,new Date().toISOString()),u.debug("DB","Successfully added hierarchical fields to observations table")}makeObservationsTextNullable(){if(this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(9))return;let s=this.db.query("PRAGMA table_info(observations)").all().find(r=>r.name==="text");if(!s||s.notnull===0){this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(9,new Date().toISOString());return}u.debug("DB","Making observations.text nullable"),this.db.run("BEGIN TRANSACTION"),this.db.run(`
      CREATE TABLE observations_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_session_id TEXT NOT NULL,
        project TEXT NOT NULL,
        text TEXT,
        type TEXT NOT NULL CHECK(type IN ('decision', 'bugfix', 'feature', 'refactor', 'discovery', 'change')),
        title TEXT,
        subtitle TEXT,
        facts TEXT,
        narrative TEXT,
        concepts TEXT,
        files_read TEXT,
        files_modified TEXT,
        prompt_number INTEGER,
        created_at TEXT NOT NULL,
        created_at_epoch INTEGER NOT NULL,
        FOREIGN KEY(memory_session_id) REFERENCES sdk_sessions(memory_session_id) ON DELETE CASCADE
      )
    `),this.db.run(`
      INSERT INTO observations_new
      SELECT id, memory_session_id, project, text, type, title, subtitle, facts,
             narrative, concepts, files_read, files_modified, prompt_number,
             created_at, created_at_epoch
      FROM observations
    `),this.db.run("DROP TABLE observations"),this.db.run("ALTER TABLE observations_new RENAME TO observations"),this.db.run(`
      CREATE INDEX idx_observations_sdk_session ON observations(memory_session_id);
      CREATE INDEX idx_observations_project ON observations(project);
      CREATE INDEX idx_observations_type ON observations(type);
      CREATE INDEX idx_observations_created ON observations(created_at_epoch DESC);
    `),this.db.run("COMMIT"),this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(9,new Date().toISOString()),u.debug("DB","Successfully made observations.text nullable")}createUserPromptsTable(){if(this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(10))return;if(this.db.query("PRAGMA table_info(user_prompts)").all().length>0){this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(10,new Date().toISOString());return}u.debug("DB","Creating user_prompts table with FTS5 support"),this.db.run("BEGIN TRANSACTION"),this.db.run(`
      CREATE TABLE user_prompts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content_session_id TEXT NOT NULL,
        prompt_number INTEGER NOT NULL,
        prompt_text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        created_at_epoch INTEGER NOT NULL,
        FOREIGN KEY(content_session_id) REFERENCES sdk_sessions(content_session_id) ON DELETE CASCADE
      );

      CREATE INDEX idx_user_prompts_claude_session ON user_prompts(content_session_id);
      CREATE INDEX idx_user_prompts_created ON user_prompts(created_at_epoch DESC);
      CREATE INDEX idx_user_prompts_prompt_number ON user_prompts(prompt_number);
      CREATE INDEX idx_user_prompts_lookup ON user_prompts(content_session_id, prompt_number);
    `),this.db.run(`
      CREATE VIRTUAL TABLE user_prompts_fts USING fts5(
        prompt_text,
        content='user_prompts',
        content_rowid='id'
      );
    `),this.db.run(`
      CREATE TRIGGER user_prompts_ai AFTER INSERT ON user_prompts BEGIN
        INSERT INTO user_prompts_fts(rowid, prompt_text)
        VALUES (new.id, new.prompt_text);
      END;

      CREATE TRIGGER user_prompts_ad AFTER DELETE ON user_prompts BEGIN
        INSERT INTO user_prompts_fts(user_prompts_fts, rowid, prompt_text)
        VALUES('delete', old.id, old.prompt_text);
      END;

      CREATE TRIGGER user_prompts_au AFTER UPDATE ON user_prompts BEGIN
        INSERT INTO user_prompts_fts(user_prompts_fts, rowid, prompt_text)
        VALUES('delete', old.id, old.prompt_text);
        INSERT INTO user_prompts_fts(rowid, prompt_text)
        VALUES (new.id, new.prompt_text);
      END;
    `),this.db.run("COMMIT"),this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(10,new Date().toISOString()),u.debug("DB","Successfully created user_prompts table with FTS5 support")}ensureDiscoveryTokensColumn(){if(this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(11))return;this.db.query("PRAGMA table_info(observations)").all().some(i=>i.name==="discovery_tokens")||(this.db.run("ALTER TABLE observations ADD COLUMN discovery_tokens INTEGER DEFAULT 0"),u.debug("DB","Added discovery_tokens column to observations table")),this.db.query("PRAGMA table_info(session_summaries)").all().some(i=>i.name==="discovery_tokens")||(this.db.run("ALTER TABLE session_summaries ADD COLUMN discovery_tokens INTEGER DEFAULT 0"),u.debug("DB","Added discovery_tokens column to session_summaries table")),this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(11,new Date().toISOString())}createPendingMessagesTable(){if(this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(16))return;if(this.db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_messages'").all().length>0){this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(16,new Date().toISOString());return}u.debug("DB","Creating pending_messages table"),this.db.run(`
      CREATE TABLE pending_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_db_id INTEGER NOT NULL,
        content_session_id TEXT NOT NULL,
        message_type TEXT NOT NULL CHECK(message_type IN ('observation', 'summarize')),
        tool_name TEXT,
        tool_input TEXT,
        tool_response TEXT,
        cwd TEXT,
        last_user_message TEXT,
        last_assistant_message TEXT,
        prompt_number INTEGER,
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'processed', 'failed')),
        retry_count INTEGER NOT NULL DEFAULT 0,
        created_at_epoch INTEGER NOT NULL,
        started_processing_at_epoch INTEGER,
        completed_at_epoch INTEGER,
        FOREIGN KEY (session_db_id) REFERENCES sdk_sessions(id) ON DELETE CASCADE
      )
    `),this.db.run("CREATE INDEX IF NOT EXISTS idx_pending_messages_session ON pending_messages(session_db_id)"),this.db.run("CREATE INDEX IF NOT EXISTS idx_pending_messages_status ON pending_messages(status)"),this.db.run("CREATE INDEX IF NOT EXISTS idx_pending_messages_claude_session ON pending_messages(content_session_id)"),this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(16,new Date().toISOString()),u.debug("DB","pending_messages table created successfully")}renameSessionIdColumns(){if(this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(17))return;u.debug("DB","Checking session ID columns for semantic clarity rename");let t=0,s=(r,o,i)=>{let d=this.db.query(`PRAGMA table_info(${r})`).all(),a=d.some(m=>m.name===o);return d.some(m=>m.name===i)?!1:a?(this.db.run(`ALTER TABLE ${r} RENAME COLUMN ${o} TO ${i}`),u.debug("DB",`Renamed ${r}.${o} to ${i}`),!0):(u.warn("DB",`Column ${o} not found in ${r}, skipping rename`),!1)};s("sdk_sessions","claude_session_id","content_session_id")&&t++,s("sdk_sessions","sdk_session_id","memory_session_id")&&t++,s("pending_messages","claude_session_id","content_session_id")&&t++,s("observations","sdk_session_id","memory_session_id")&&t++,s("session_summaries","sdk_session_id","memory_session_id")&&t++,s("user_prompts","claude_session_id","content_session_id")&&t++,this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(17,new Date().toISOString()),t>0?u.debug("DB",`Successfully renamed ${t} session ID columns`):u.debug("DB","No session ID column renames needed (already up to date)")}repairSessionIdColumnRename(){this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(19)||this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(19,new Date().toISOString())}addFailedAtEpochColumn(){if(this.db.prepare("SELECT version FROM schema_versions WHERE version = ?").get(20))return;this.db.query("PRAGMA table_info(pending_messages)").all().some(r=>r.name==="failed_at_epoch")||(this.db.run("ALTER TABLE pending_messages ADD COLUMN failed_at_epoch INTEGER"),u.debug("DB","Added failed_at_epoch column to pending_messages table")),this.db.prepare("INSERT OR IGNORE INTO schema_versions (version, applied_at) VALUES (?, ?)").run(20,new Date().toISOString())}updateMemorySessionId(e,t){this.db.prepare(`
      UPDATE sdk_sessions
      SET memory_session_id = ?
      WHERE id = ?
    `).run(t,e)}getRecentSummaries(e,t=10){return this.db.prepare(`
      SELECT
        request, investigated, learned, completed, next_steps,
        files_read, files_edited, notes, prompt_number, created_at
      FROM session_summaries
      WHERE project = ?
      ORDER BY created_at_epoch DESC
      LIMIT ?
    `).all(e,t)}getRecentSummariesWithSessionInfo(e,t=3){return this.db.prepare(`
      SELECT
        memory_session_id, request, learned, completed, next_steps,
        prompt_number, created_at
      FROM session_summaries
      WHERE project = ?
      ORDER BY created_at_epoch DESC
      LIMIT ?
    `).all(e,t)}getRecentObservations(e,t=20){return this.db.prepare(`
      SELECT type, text, prompt_number, created_at
      FROM observations
      WHERE project = ?
      ORDER BY created_at_epoch DESC
      LIMIT ?
    `).all(e,t)}getAllRecentObservations(e=100){return this.db.prepare(`
      SELECT id, type, title, subtitle, text, project, prompt_number, created_at, created_at_epoch
      FROM observations
      ORDER BY created_at_epoch DESC
      LIMIT ?
    `).all(e)}getAllRecentSummaries(e=50){return this.db.prepare(`
      SELECT id, request, investigated, learned, completed, next_steps,
             files_read, files_edited, notes, project, prompt_number,
             created_at, created_at_epoch
      FROM session_summaries
      ORDER BY created_at_epoch DESC
      LIMIT ?
    `).all(e)}getAllRecentUserPrompts(e=100){return this.db.prepare(`
      SELECT
        up.id,
        up.content_session_id,
        s.project,
        up.prompt_number,
        up.prompt_text,
        up.created_at,
        up.created_at_epoch
      FROM user_prompts up
      LEFT JOIN sdk_sessions s ON up.content_session_id = s.content_session_id
      ORDER BY up.created_at_epoch DESC
      LIMIT ?
    `).all(e)}getAllProjects(){return this.db.prepare(`
      SELECT DISTINCT project
      FROM sdk_sessions
      WHERE project IS NOT NULL AND project != ''
      ORDER BY project ASC
    `).all().map(s=>s.project)}getLatestUserPrompt(e){return this.db.prepare(`
      SELECT
        up.*,
        s.memory_session_id,
        s.project
      FROM user_prompts up
      JOIN sdk_sessions s ON up.content_session_id = s.content_session_id
      WHERE up.content_session_id = ?
      ORDER BY up.created_at_epoch DESC
      LIMIT 1
    `).get(e)}getRecentSessionsWithStatus(e,t=3){return this.db.prepare(`
      SELECT * FROM (
        SELECT
          s.memory_session_id,
          s.status,
          s.started_at,
          s.started_at_epoch,
          s.user_prompt,
          CASE WHEN sum.memory_session_id IS NOT NULL THEN 1 ELSE 0 END as has_summary
        FROM sdk_sessions s
        LEFT JOIN session_summaries sum ON s.memory_session_id = sum.memory_session_id
        WHERE s.project = ? AND s.memory_session_id IS NOT NULL
        GROUP BY s.memory_session_id
        ORDER BY s.started_at_epoch DESC
        LIMIT ?
      )
      ORDER BY started_at_epoch ASC
    `).all(e,t)}getObservationsForSession(e){return this.db.prepare(`
      SELECT title, subtitle, type, prompt_number
      FROM observations
      WHERE memory_session_id = ?
      ORDER BY created_at_epoch ASC
    `).all(e)}getObservationById(e){return this.db.prepare(`
      SELECT *
      FROM observations
      WHERE id = ?
    `).get(e)||null}getObservationsByIds(e,t={}){if(e.length===0)return[];let{orderBy:s="date_desc",limit:r,project:o,type:i,concepts:d,files:a}=t,p=s==="date_asc"?"ASC":"DESC",m=r?`LIMIT ${r}`:"",l=e.map(()=>"?").join(","),g=[...e],E=[];if(o&&(E.push("project = ?"),g.push(o)),i)if(Array.isArray(i)){let _=i.map(()=>"?").join(",");E.push(`type IN (${_})`),g.push(...i)}else E.push("type = ?"),g.push(i);if(d){let _=Array.isArray(d)?d:[d],S=_.map(()=>"EXISTS (SELECT 1 FROM json_each(concepts) WHERE value = ?)");g.push(..._),E.push(`(${S.join(" OR ")})`)}if(a){let _=Array.isArray(a)?a:[a],S=_.map(()=>"(EXISTS (SELECT 1 FROM json_each(files_read) WHERE value LIKE ?) OR EXISTS (SELECT 1 FROM json_each(files_modified) WHERE value LIKE ?))");_.forEach(f=>{g.push(`%${f}%`,`%${f}%`)}),E.push(`(${S.join(" OR ")})`)}let T=E.length>0?`WHERE id IN (${l}) AND ${E.join(" AND ")}`:`WHERE id IN (${l})`;return this.db.prepare(`
      SELECT *
      FROM observations
      ${T}
      ORDER BY created_at_epoch ${p}
      ${m}
    `).all(...g)}deleteObservation(e){return this.db.prepare("DELETE FROM observations WHERE id = ?").run(e).changes>0}deleteObservations(e){if(e.length===0)return 0;let t=e.map(()=>"?").join(",");return this.db.prepare(`DELETE FROM observations WHERE id IN (${t})`).run(...e).changes}getSummaryForSession(e){return this.db.prepare(`
      SELECT
        request, investigated, learned, completed, next_steps,
        files_read, files_edited, notes, prompt_number, created_at,
        created_at_epoch
      FROM session_summaries
      WHERE memory_session_id = ?
      ORDER BY created_at_epoch DESC
      LIMIT 1
    `).get(e)||null}getFilesForSession(e){let s=this.db.prepare(`
      SELECT files_read, files_modified
      FROM observations
      WHERE memory_session_id = ?
    `).all(e),r=new Set,o=new Set;for(let i of s){if(i.files_read){let d=JSON.parse(i.files_read);Array.isArray(d)&&d.forEach(a=>r.add(a))}if(i.files_modified){let d=JSON.parse(i.files_modified);Array.isArray(d)&&d.forEach(a=>o.add(a))}}return{filesRead:Array.from(r),filesModified:Array.from(o)}}getSessionById(e){return this.db.prepare(`
      SELECT id, content_session_id, memory_session_id, project, user_prompt
      FROM sdk_sessions
      WHERE id = ?
      LIMIT 1
    `).get(e)||null}getSdkSessionsBySessionIds(e){if(e.length===0)return[];let t=e.map(()=>"?").join(",");return this.db.prepare(`
      SELECT id, content_session_id, memory_session_id, project, user_prompt,
             started_at, started_at_epoch, completed_at, completed_at_epoch, status
      FROM sdk_sessions
      WHERE memory_session_id IN (${t})
      ORDER BY started_at_epoch DESC
    `).all(...e)}getPromptNumberFromUserPrompts(e){return this.db.prepare(`
      SELECT COUNT(*) as count FROM user_prompts WHERE content_session_id = ?
    `).get(e).count}createSDKSession(e,t,s){let r=new Date,o=r.getTime(),i=crypto.randomUUID();return this.db.prepare(`
      INSERT OR IGNORE INTO sdk_sessions
      (content_session_id, memory_session_id, project, user_prompt, started_at, started_at_epoch, status)
      VALUES (?, ?, ?, ?, ?, ?, 'active')
    `).run(e,i,t,s,r.toISOString(),o),this.db.prepare("SELECT id FROM sdk_sessions WHERE content_session_id = ?").get(e).id}saveUserPrompt(e,t,s){let r=new Date,o=r.getTime();return this.db.prepare(`
      INSERT INTO user_prompts
      (content_session_id, prompt_number, prompt_text, created_at, created_at_epoch)
      VALUES (?, ?, ?, ?, ?)
    `).run(e,t,s,r.toISOString(),o).lastInsertRowid}getUserPrompt(e,t){return this.db.prepare(`
      SELECT prompt_text
      FROM user_prompts
      WHERE content_session_id = ? AND prompt_number = ?
      LIMIT 1
    `).get(e,t)?.prompt_text??null}storeObservation(e,t,s,r,o=0,i){let d=i??Date.now(),a=new Date(d).toISOString(),m=this.db.prepare(`
      INSERT INTO observations
      (memory_session_id, project, type, title, subtitle, facts, narrative, concepts,
       files_read, files_modified, prompt_number, discovery_tokens, created_at, created_at_epoch)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(e,t,s.type,s.title,s.subtitle,JSON.stringify(s.facts),s.narrative,JSON.stringify(s.concepts),JSON.stringify(s.files_read),JSON.stringify(s.files_modified),r||null,o,a,d);return{id:Number(m.lastInsertRowid),createdAtEpoch:d}}storeSummary(e,t,s,r,o=0,i){let d=i??Date.now(),a=new Date(d).toISOString(),m=this.db.prepare(`
      INSERT INTO session_summaries
      (memory_session_id, project, request, investigated, learned, completed,
       next_steps, notes, prompt_number, discovery_tokens, created_at, created_at_epoch)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(e,t,s.request,s.investigated,s.learned,s.completed,s.next_steps,s.notes,r||null,o,a,d);return{id:Number(m.lastInsertRowid),createdAtEpoch:d}}storeObservations(e,t,s,r,o,i=0,d){let a=d??Date.now(),p=new Date(a).toISOString();return this.db.transaction(()=>{let l=[],g=this.db.prepare(`
        INSERT INTO observations
        (memory_session_id, project, type, title, subtitle, facts, narrative, concepts,
         files_read, files_modified, prompt_number, discovery_tokens, created_at, created_at_epoch)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);for(let T of s){let h=g.run(e,t,T.type,T.title,T.subtitle,JSON.stringify(T.facts),T.narrative,JSON.stringify(T.concepts),JSON.stringify(T.files_read),JSON.stringify(T.files_modified),o||null,i,p,a);l.push(Number(h.lastInsertRowid))}let E=null;if(r){let h=this.db.prepare(`
          INSERT INTO session_summaries
          (memory_session_id, project, request, investigated, learned, completed,
           next_steps, notes, prompt_number, discovery_tokens, created_at, created_at_epoch)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).run(e,t,r.request,r.investigated,r.learned,r.completed,r.next_steps,r.notes,o||null,i,p,a);E=Number(h.lastInsertRowid)}return{observationIds:l,summaryId:E,createdAtEpoch:a}})()}storeObservationsAndMarkComplete(e,t,s,r,o,i,d,a=0,p){let m=p??Date.now(),l=new Date(m).toISOString();return this.db.transaction(()=>{let E=[],T=this.db.prepare(`
        INSERT INTO observations
        (memory_session_id, project, type, title, subtitle, facts, narrative, concepts,
         files_read, files_modified, prompt_number, discovery_tokens, created_at, created_at_epoch)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);for(let S of s){let f=T.run(e,t,S.type,S.title,S.subtitle,JSON.stringify(S.facts),S.narrative,JSON.stringify(S.concepts),JSON.stringify(S.files_read),JSON.stringify(S.files_modified),d||null,a,l,m);E.push(Number(f.lastInsertRowid))}let h;if(r){let f=this.db.prepare(`
          INSERT INTO session_summaries
          (memory_session_id, project, request, investigated, learned, completed,
           next_steps, notes, prompt_number, discovery_tokens, created_at, created_at_epoch)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).run(e,t,r.request,r.investigated,r.learned,r.completed,r.next_steps,r.notes,d||null,a,l,m);h=Number(f.lastInsertRowid)}return this.db.prepare(`
        UPDATE pending_messages
        SET
          status = 'processed',
          completed_at_epoch = ?,
          tool_input = NULL,
          tool_response = NULL
        WHERE id = ? AND status = 'processing'
      `).run(m,o),{observationIds:E,summaryId:h,createdAtEpoch:m}})()}getSessionSummariesByIds(e,t={}){if(e.length===0)return[];let{orderBy:s="date_desc",limit:r,project:o}=t,i=s==="date_asc"?"ASC":"DESC",d=r?`LIMIT ${r}`:"",a=e.map(()=>"?").join(","),p=[...e],m=o?`WHERE id IN (${a}) AND project = ?`:`WHERE id IN (${a})`;return o&&p.push(o),this.db.prepare(`
      SELECT * FROM session_summaries
      ${m}
      ORDER BY created_at_epoch ${i}
      ${d}
    `).all(...p)}getUserPromptsByIds(e,t={}){if(e.length===0)return[];let{orderBy:s="date_desc",limit:r,project:o}=t,i=s==="date_asc"?"ASC":"DESC",d=r?`LIMIT ${r}`:"",a=e.map(()=>"?").join(","),p=[...e],m=o?"AND s.project = ?":"";return o&&p.push(o),this.db.prepare(`
      SELECT
        up.*,
        s.project,
        s.memory_session_id
      FROM user_prompts up
      JOIN sdk_sessions s ON up.content_session_id = s.content_session_id
      WHERE up.id IN (${a}) ${m}
      ORDER BY up.created_at_epoch ${i}
      ${d}
    `).all(...p)}getTimelineAroundTimestamp(e,t=10,s=10,r){return this.getTimelineAroundObservation(null,e,t,s,r)}getTimelineAroundObservation(e,t,s=10,r=10,o){let i=o?"AND project = ?":"",d=o?[o]:[],a,p;if(e!==null){let _=`
        SELECT id, created_at_epoch
        FROM observations
        WHERE id <= ? ${i}
        ORDER BY id DESC
        LIMIT ?
      `,S=`
        SELECT id, created_at_epoch
        FROM observations
        WHERE id >= ? ${i}
        ORDER BY id ASC
        LIMIT ?
      `;try{let f=this.db.prepare(_).all(e,...d,s+1),C=this.db.prepare(S).all(e,...d,r+1);if(f.length===0&&C.length===0)return{observations:[],sessions:[],prompts:[]};a=f.length>0?f[f.length-1].created_at_epoch:t,p=C.length>0?C[C.length-1].created_at_epoch:t}catch(f){return u.error("DB","Error getting boundary observations",void 0,{error:f,project:o}),{observations:[],sessions:[],prompts:[]}}}else{let _=`
        SELECT created_at_epoch
        FROM observations
        WHERE created_at_epoch <= ? ${i}
        ORDER BY created_at_epoch DESC
        LIMIT ?
      `,S=`
        SELECT created_at_epoch
        FROM observations
        WHERE created_at_epoch >= ? ${i}
        ORDER BY created_at_epoch ASC
        LIMIT ?
      `;try{let f=this.db.prepare(_).all(t,...d,s),C=this.db.prepare(S).all(t,...d,r+1);if(f.length===0&&C.length===0)return{observations:[],sessions:[],prompts:[]};a=f.length>0?f[f.length-1].created_at_epoch:t,p=C.length>0?C[C.length-1].created_at_epoch:t}catch(f){return u.error("DB","Error getting boundary timestamps",void 0,{error:f,project:o}),{observations:[],sessions:[],prompts:[]}}}let m=`
      SELECT *
      FROM observations
      WHERE created_at_epoch >= ? AND created_at_epoch <= ? ${i}
      ORDER BY created_at_epoch ASC
    `,l=`
      SELECT *
      FROM session_summaries
      WHERE created_at_epoch >= ? AND created_at_epoch <= ? ${i}
      ORDER BY created_at_epoch ASC
    `,g=`
      SELECT up.*, s.project, s.memory_session_id
      FROM user_prompts up
      JOIN sdk_sessions s ON up.content_session_id = s.content_session_id
      WHERE up.created_at_epoch >= ? AND up.created_at_epoch <= ? ${i.replace("project","s.project")}
      ORDER BY up.created_at_epoch ASC
    `,E=this.db.prepare(m).all(a,p,...d),T=this.db.prepare(l).all(a,p,...d),h=this.db.prepare(g).all(a,p,...d);return{observations:E,sessions:T.map(_=>({id:_.id,memory_session_id:_.memory_session_id,project:_.project,request:_.request,completed:_.completed,next_steps:_.next_steps,created_at:_.created_at,created_at_epoch:_.created_at_epoch})),prompts:h.map(_=>({id:_.id,content_session_id:_.content_session_id,prompt_number:_.prompt_number,prompt_text:_.prompt_text,project:_.project,created_at:_.created_at,created_at_epoch:_.created_at_epoch}))}}getPromptById(e){return this.db.prepare(`
      SELECT
        p.id,
        p.content_session_id,
        p.prompt_number,
        p.prompt_text,
        s.project,
        p.created_at,
        p.created_at_epoch
      FROM user_prompts p
      LEFT JOIN sdk_sessions s ON p.content_session_id = s.content_session_id
      WHERE p.id = ?
      LIMIT 1
    `).get(e)||null}getPromptsByIds(e){if(e.length===0)return[];let t=e.map(()=>"?").join(",");return this.db.prepare(`
      SELECT
        p.id,
        p.content_session_id,
        p.prompt_number,
        p.prompt_text,
        s.project,
        p.created_at,
        p.created_at_epoch
      FROM user_prompts p
      LEFT JOIN sdk_sessions s ON p.content_session_id = s.content_session_id
      WHERE p.id IN (${t})
      ORDER BY p.created_at_epoch DESC
    `).all(...e)}getSessionSummaryById(e){return this.db.prepare(`
      SELECT
        id,
        memory_session_id,
        content_session_id,
        project,
        user_prompt,
        request_summary,
        learned_summary,
        status,
        created_at,
        created_at_epoch
      FROM sdk_sessions
      WHERE id = ?
      LIMIT 1
    `).get(e)||null}getOrCreateManualSession(e){let t=`manual-${e}`,s=`manual-content-${e}`;if(this.db.prepare("SELECT memory_session_id FROM sdk_sessions WHERE memory_session_id = ?").get(t))return t;let o=new Date;return this.db.prepare(`
      INSERT INTO sdk_sessions (memory_session_id, content_session_id, project, started_at, started_at_epoch, status)
      VALUES (?, ?, ?, ?, ?, 'active')
    `).run(t,s,e,o.toISOString(),o.getTime()),u.info("SESSION","Created manual session",{memorySessionId:t,project:e}),t}close(){this.db.close()}importSdkSession(e){let t=this.db.prepare("SELECT id FROM sdk_sessions WHERE content_session_id = ?").get(e.content_session_id);return t?{imported:!1,id:t.id}:{imported:!0,id:this.db.prepare(`
      INSERT INTO sdk_sessions (
        content_session_id, memory_session_id, project, user_prompt,
        started_at, started_at_epoch, completed_at, completed_at_epoch, status
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(e.content_session_id,e.memory_session_id,e.project,e.user_prompt,e.started_at,e.started_at_epoch,e.completed_at,e.completed_at_epoch,e.status).lastInsertRowid}}importSessionSummary(e){let t=this.db.prepare("SELECT id FROM session_summaries WHERE memory_session_id = ?").get(e.memory_session_id);return t?{imported:!1,id:t.id}:{imported:!0,id:this.db.prepare(`
      INSERT INTO session_summaries (
        memory_session_id, project, request, investigated, learned,
        completed, next_steps, files_read, files_edited, notes,
        prompt_number, discovery_tokens, created_at, created_at_epoch
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(e.memory_session_id,e.project,e.request,e.investigated,e.learned,e.completed,e.next_steps,e.files_read,e.files_edited,e.notes,e.prompt_number,e.discovery_tokens||0,e.created_at,e.created_at_epoch).lastInsertRowid}}importObservation(e){let t=this.db.prepare(`
      SELECT id FROM observations
      WHERE memory_session_id = ? AND title = ? AND created_at_epoch = ?
    `).get(e.memory_session_id,e.title,e.created_at_epoch);return t?{imported:!1,id:t.id}:{imported:!0,id:this.db.prepare(`
      INSERT INTO observations (
        memory_session_id, project, text, type, title, subtitle,
        facts, narrative, concepts, files_read, files_modified,
        prompt_number, discovery_tokens, created_at, created_at_epoch
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(e.memory_session_id,e.project,e.text,e.type,e.title,e.subtitle,e.facts,e.narrative,e.concepts,e.files_read,e.files_modified,e.prompt_number,e.discovery_tokens||0,e.created_at,e.created_at_epoch).lastInsertRowid}}importUserPrompt(e){let t=this.db.prepare(`
      SELECT id FROM user_prompts
      WHERE content_session_id = ? AND prompt_number = ?
    `).get(e.content_session_id,e.prompt_number);return t?{imported:!1,id:t.id}:{imported:!0,id:this.db.prepare(`
      INSERT INTO user_prompts (
        content_session_id, prompt_number, prompt_text,
        created_at, created_at_epoch
      ) VALUES (?, ?, ?, ?, ?)
    `).run(e.content_session_id,e.prompt_number,e.prompt_text,e.created_at,e.created_at_epoch).lastInsertRowid}}getAllTags(){return this.db.prepare(`
      SELECT * FROM tags
      ORDER BY usage_count DESC, name ASC
    `).all()}getOrCreateTag(e,t){let s=e.toLowerCase().trim(),r=this.db.prepare(`
      SELECT id, name, color FROM tags WHERE name = ?
    `).get(s);if(r)return{...r,created:!1};let o=new Date;return{id:this.db.prepare(`
      INSERT INTO tags (name, color, created_at, created_at_epoch)
      VALUES (?, ?, ?, ?)
    `).run(s,t||"#6b7280",o.toISOString(),o.getTime()).lastInsertRowid,name:s,color:t||"#6b7280",created:!0}}updateTag(e,t){let s=[],r=[];return t.name!==void 0&&(s.push("name = ?"),r.push(t.name.toLowerCase().trim())),t.color!==void 0&&(s.push("color = ?"),r.push(t.color)),t.description!==void 0&&(s.push("description = ?"),r.push(t.description)),s.length===0?!1:(r.push(e),this.db.prepare(`
      UPDATE tags SET ${s.join(", ")} WHERE id = ?
    `).run(...r).changes>0)}deleteTag(e){return this.db.prepare("DELETE FROM tags WHERE id = ?").run(e).changes>0}addTagsToObservation(e,t){let s=this.getObservationById(e);if(!s)return;let r=[];try{r=s.tags?JSON.parse(s.tags):[]}catch{r=[]}let o=t.map(a=>a.toLowerCase().trim()),i=[...new Set([...r,...o])];this.db.prepare("UPDATE observations SET tags = ? WHERE id = ?").run(JSON.stringify(i),e);for(let a of o)r.includes(a)||(this.getOrCreateTag(a),this.db.prepare("UPDATE tags SET usage_count = usage_count + 1 WHERE name = ?").run(a))}removeTagsFromObservation(e,t){let s=this.getObservationById(e);if(!s)return;let r=[];try{r=s.tags?JSON.parse(s.tags):[]}catch{r=[]}let o=t.map(a=>a.toLowerCase().trim()),i=r.filter(a=>!o.includes(a));this.db.prepare("UPDATE observations SET tags = ? WHERE id = ?").run(JSON.stringify(i),e);for(let a of o)r.includes(a)&&this.db.prepare("UPDATE tags SET usage_count = MAX(0, usage_count - 1) WHERE name = ?").run(a)}getObservationTags(e){let t=this.getObservationById(e);if(!t?.tags)return[];try{return JSON.parse(t.tags)}catch{return[]}}getObservationsByTags(e,t={}){let{matchAll:s=!1,limit:r=50,project:o}=t,i=e.map(m=>m.toLowerCase().trim()),d,a=[];return s?(d=`SELECT * FROM observations WHERE tags IS NOT NULL AND ${i.map(()=>"EXISTS (SELECT 1 FROM json_each(tags) WHERE value = ?)").join(" AND ")}`,a.push(...i)):(d=`SELECT * FROM observations WHERE tags IS NOT NULL AND (${i.map(()=>"EXISTS (SELECT 1 FROM json_each(tags) WHERE value = ?)").join(" OR ")})`,a.push(...i)),o&&(d+=" AND project = ?",a.push(o)),d+=" ORDER BY created_at_epoch DESC LIMIT ?",a.push(r),this.db.prepare(d).all(...a)}getPopularTags(e=20){return this.db.prepare(`
      SELECT name, color, usage_count FROM tags
      WHERE usage_count > 0
      ORDER BY usage_count DESC
      LIMIT ?
    `).all(e)}suggestTagsForObservation(e){let t=this.getObservationById(e);if(!t)return[];let s=[];if(t.concepts)try{let i=JSON.parse(t.concepts);s.push(...i)}catch{typeof t.concepts=="string"&&s.push(...t.concepts.split(",").map(i=>i.trim()))}t.type&&s.push(t.type);let r=this.getAllTags(),o=new Set(r.map(i=>i.name));return[...new Set(s.map(i=>i.toLowerCase().trim()))].filter(Boolean)}};var Ee=L(require("path"),1);function ge(n){if(!n||n.trim()==="")return u.warn("PROJECT_NAME","Empty cwd provided, using fallback",{cwd:n}),"unknown-project";let e=Ee.default.basename(n);if(e===""){if(process.platform==="win32"){let s=n.match(/^([A-Z]):\\/i);if(s){let o=`drive-${s[1].toUpperCase()}`;return u.info("PROJECT_NAME","Drive root detected",{cwd:n,projectName:o}),o}}return u.warn("PROJECT_NAME","Root directory detected, using fallback",{cwd:n}),"unknown-project"}return e}var Te=L(require("path"),1),fe=require("os");var v=require("fs"),P=require("path");var O=class n{static instance=null;activeMode=null;modesDir;constructor(){let e=le(),t=[(0,P.join)(e,"modes"),(0,P.join)(e,"..","plugin","modes")],s=t.find(r=>(0,v.existsSync)(r));this.modesDir=s||t[0]}static getInstance(){return n.instance||(n.instance=new n),n.instance}parseInheritance(e){let t=e.split("--");if(t.length===1)return{hasParent:!1,parentId:"",overrideId:""};if(t.length>2)throw new Error(`Invalid mode inheritance: ${e}. Only one level of inheritance supported (parent--override)`);return{hasParent:!0,parentId:t[0],overrideId:e}}isPlainObject(e){return e!==null&&typeof e=="object"&&!Array.isArray(e)}deepMerge(e,t){let s={...e};for(let r in t){let o=t[r],i=e[r];this.isPlainObject(o)&&this.isPlainObject(i)?s[r]=this.deepMerge(i,o):s[r]=o}return s}loadModeFile(e){let t=(0,P.join)(this.modesDir,`${e}.json`);if(!(0,v.existsSync)(t))throw new Error(`Mode file not found: ${t}`);let s=(0,v.readFileSync)(t,"utf-8");return JSON.parse(s)}loadMode(e){let t=this.parseInheritance(e);if(!t.hasParent)try{let a=this.loadModeFile(e);return this.activeMode=a,u.debug("SYSTEM",`Loaded mode: ${a.name} (${e})`,void 0,{types:a.observation_types.map(p=>p.id),concepts:a.observation_concepts.map(p=>p.id)}),a}catch{if(u.warn("SYSTEM",`Mode file not found: ${e}, falling back to 'code'`),e==="code")throw new Error("Critical: code.json mode file missing");return this.loadMode("code")}let{parentId:s,overrideId:r}=t,o;try{o=this.loadMode(s)}catch{u.warn("SYSTEM",`Parent mode '${s}' not found for ${e}, falling back to 'code'`),o=this.loadMode("code")}let i;try{i=this.loadModeFile(r),u.debug("SYSTEM",`Loaded override file: ${r} for parent ${s}`)}catch{return u.warn("SYSTEM",`Override file '${r}' not found, using parent mode '${s}' only`),this.activeMode=o,o}if(!i)return u.warn("SYSTEM",`Invalid override file: ${r}, using parent mode '${s}' only`),this.activeMode=o,o;let d=this.deepMerge(o,i);return this.activeMode=d,u.debug("SYSTEM",`Loaded mode with inheritance: ${d.name} (${e} = ${s} + ${r})`,void 0,{parent:s,override:r,types:d.observation_types.map(a=>a.id),concepts:d.observation_concepts.map(a=>a.id)}),d}getActiveMode(){if(!this.activeMode)throw new Error("No mode loaded. Call loadMode() first.");return this.activeMode}getObservationTypes(){return this.getActiveMode().observation_types}getObservationConcepts(){return this.getActiveMode().observation_concepts}getTypeIcon(e){return this.getObservationTypes().find(s=>s.id===e)?.emoji||"\u{1F4DD}"}getWorkEmoji(e){return this.getObservationTypes().find(s=>s.id===e)?.work_emoji||"\u{1F4DD}"}validateType(e){return this.getObservationTypes().some(t=>t.id===e)}getTypeLabel(e){return this.getObservationTypes().find(s=>s.id===e)?.label||e}};function V(){let n=Te.default.join((0,fe.homedir)(),".claude-mem","settings.json"),e=A.loadFromFile(n),t=e.CLAUDE_MEM_MODE,s=t==="code"||t.startsWith("code--"),r,o;if(s)r=new Set(e.CLAUDE_MEM_CONTEXT_OBSERVATION_TYPES.split(",").map(i=>i.trim()).filter(Boolean)),o=new Set(e.CLAUDE_MEM_CONTEXT_OBSERVATION_CONCEPTS.split(",").map(i=>i.trim()).filter(Boolean));else{let i=O.getInstance().getActiveMode();r=new Set(i.observation_types.map(d=>d.id)),o=new Set(i.observation_concepts.map(d=>d.id))}return{totalObservationCount:parseInt(e.CLAUDE_MEM_CONTEXT_OBSERVATIONS,10),fullObservationCount:parseInt(e.CLAUDE_MEM_CONTEXT_FULL_COUNT,10),sessionCount:parseInt(e.CLAUDE_MEM_CONTEXT_SESSION_COUNT,10),showReadTokens:e.CLAUDE_MEM_CONTEXT_SHOW_READ_TOKENS,showWorkTokens:e.CLAUDE_MEM_CONTEXT_SHOW_WORK_TOKENS,showSavingsAmount:e.CLAUDE_MEM_CONTEXT_SHOW_SAVINGS_AMOUNT,showSavingsPercent:e.CLAUDE_MEM_CONTEXT_SHOW_SAVINGS_PERCENT,observationTypes:r,observationConcepts:o,fullObservationField:e.CLAUDE_MEM_CONTEXT_FULL_FIELD,showLastSummary:e.CLAUDE_MEM_CONTEXT_SHOW_LAST_SUMMARY,showLastMessage:e.CLAUDE_MEM_CONTEXT_SHOW_LAST_MESSAGE}}var c={reset:"\x1B[0m",bright:"\x1B[1m",dim:"\x1B[2m",cyan:"\x1B[36m",green:"\x1B[32m",yellow:"\x1B[33m",blue:"\x1B[34m",magenta:"\x1B[35m",gray:"\x1B[90m",red:"\x1B[31m"},Se=4,K=1;function q(n){let e=(n.title?.length||0)+(n.subtitle?.length||0)+(n.narrative?.length||0)+JSON.stringify(n.facts||[]).length;return Math.ceil(e/Se)}function J(n){let e=n.length,t=n.reduce((i,d)=>i+q(d),0),s=n.reduce((i,d)=>i+(d.discovery_tokens||0),0),r=s-t,o=s>0?Math.round(r/s*100):0;return{totalObservations:e,totalReadTokens:t,totalDiscoveryTokens:s,savings:r,savingsPercent:o}}function Mt(n){return O.getInstance().getWorkEmoji(n)}function I(n,e){let t=q(n),s=n.discovery_tokens||0,r=Mt(n.type),o=s>0?`${r} ${s.toLocaleString()}`:"-";return{readTokens:t,discoveryTokens:s,discoveryDisplay:o,workEmoji:r}}function j(n){return n.showReadTokens||n.showWorkTokens||n.showSavingsAmount||n.showSavingsPercent}var be=L(require("path"),1),he=require("os"),X=require("fs");function z(n,e,t){let s=Array.from(t.observationTypes),r=s.map(()=>"?").join(","),o=Array.from(t.observationConcepts),i=o.map(()=>"?").join(",");return n.db.prepare(`
    SELECT
      id, memory_session_id, type, title, subtitle, narrative,
      facts, concepts, files_read, files_modified, discovery_tokens,
      created_at, created_at_epoch
    FROM observations
    WHERE project = ?
      AND type IN (${r})
      AND EXISTS (
        SELECT 1 FROM json_each(concepts)
        WHERE value IN (${i})
      )
    ORDER BY created_at_epoch DESC
    LIMIT ?
  `).all(e,...s,...o,t.totalObservationCount)}function Q(n,e,t){return n.db.prepare(`
    SELECT id, memory_session_id, request, investigated, learned, completed, next_steps, created_at, created_at_epoch
    FROM session_summaries
    WHERE project = ?
    ORDER BY created_at_epoch DESC
    LIMIT ?
  `).all(e,t.sessionCount+K)}function Oe(n,e,t){let s=Array.from(t.observationTypes),r=s.map(()=>"?").join(","),o=Array.from(t.observationConcepts),i=o.map(()=>"?").join(","),d=e.map(()=>"?").join(",");return n.db.prepare(`
    SELECT
      id, memory_session_id, type, title, subtitle, narrative,
      facts, concepts, files_read, files_modified, discovery_tokens,
      created_at, created_at_epoch, project
    FROM observations
    WHERE project IN (${d})
      AND type IN (${r})
      AND EXISTS (
        SELECT 1 FROM json_each(concepts)
        WHERE value IN (${i})
      )
    ORDER BY created_at_epoch DESC
    LIMIT ?
  `).all(...e,...s,...o,t.totalObservationCount)}function Ce(n,e,t){let s=e.map(()=>"?").join(",");return n.db.prepare(`
    SELECT id, memory_session_id, request, investigated, learned, completed, next_steps, created_at, created_at_epoch, project
    FROM session_summaries
    WHERE project IN (${s})
    ORDER BY created_at_epoch DESC
    LIMIT ?
  `).all(...e,t.sessionCount+K)}function Nt(n){return n.replace(/\//g,"-")}function At(n){try{if(!(0,X.existsSync)(n))return{userMessage:"",assistantMessage:""};let e=(0,X.readFileSync)(n,"utf-8").trim();if(!e)return{userMessage:"",assistantMessage:""};let t=e.split(`
`).filter(r=>r.trim()),s="";for(let r=t.length-1;r>=0;r--)try{let o=t[r];if(!o.includes('"type":"assistant"'))continue;let i=JSON.parse(o);if(i.type==="assistant"&&i.message?.content&&Array.isArray(i.message.content)){let d="";for(let a of i.message.content)a.type==="text"&&(d+=a.text);if(d=d.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/g,"").trim(),d){s=d;break}}}catch(o){u.debug("PARSER","Skipping malformed transcript line",{lineIndex:r},o);continue}return{userMessage:"",assistantMessage:s}}catch(e){return u.failure("WORKER","Failed to extract prior messages from transcript",{transcriptPath:n},e),{userMessage:"",assistantMessage:""}}}function Z(n,e,t,s){if(!e.showLastMessage||n.length===0)return{userMessage:"",assistantMessage:""};let r=n.find(a=>a.memory_session_id!==t);if(!r)return{userMessage:"",assistantMessage:""};let o=r.memory_session_id,i=Nt(s),d=be.default.join((0,he.homedir)(),".claude","projects",i,`${o}.jsonl`);return At(d)}function Re(n,e){let t=e[0]?.id;return n.map((s,r)=>{let o=r===0?null:e[r+1];return{...s,displayEpoch:o?o.created_at_epoch:s.created_at_epoch,displayTime:o?o.created_at:s.created_at,shouldShowLink:s.id!==t}})}function ee(n,e){let t=[...n.map(s=>({type:"observation",data:s})),...e.map(s=>({type:"summary",data:s}))];return t.sort((s,r)=>{let o=s.type==="observation"?s.data.created_at_epoch:s.data.displayEpoch,i=r.type==="observation"?r.data.created_at_epoch:r.data.displayEpoch;return o-i}),t}function Me(n,e){return new Set(n.slice(0,e).map(t=>t.id))}function Ne(){let n=new Date,e=n.toLocaleDateString("en-CA"),t=n.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit",hour12:!0}).toLowerCase().replace(" ",""),s=n.toLocaleTimeString("en-US",{timeZoneName:"short"}).split(" ").pop();return`${e} ${t} ${s}`}function Ae(n){return[`# [${n}] recent context, ${Ne()}`,""]}function Ie(){return[`**Legend:** session-request | ${O.getInstance().getActiveMode().observation_types.map(t=>`${t.emoji} ${t.id}`).join(" | ")}`,""]}function Le(){return["**Column Key**:","- **Read**: Tokens to read this observation (cost to learn it now)","- **Work**: Tokens spent on work that produced this record ( research, building, deciding)",""]}function ye(){return["**Context Index:** This semantic index (titles, types, files, tokens) is usually sufficient to understand past work.","","When you need implementation details, rationale, or debugging context:","- Use MCP tools (search, get_observations) to fetch full observations on-demand","- Critical types ( bugfix, decision) often need detailed fetching","- Trust this index over re-reading code for past decisions and learnings",""]}function De(n,e){let t=[];if(t.push("**Context Economics**:"),t.push(`- Loading: ${n.totalObservations} observations (${n.totalReadTokens.toLocaleString()} tokens to read)`),t.push(`- Work investment: ${n.totalDiscoveryTokens.toLocaleString()} tokens spent on research, building, and decisions`),n.totalDiscoveryTokens>0&&(e.showSavingsAmount||e.showSavingsPercent)){let s="- Your savings: ";e.showSavingsAmount&&e.showSavingsPercent?s+=`${n.savings.toLocaleString()} tokens (${n.savingsPercent}% reduction from reuse)`:e.showSavingsAmount?s+=`${n.savings.toLocaleString()} tokens`:s+=`${n.savingsPercent}% reduction from reuse`,t.push(s)}return t.push(""),t}function ve(n){return[`### ${n}`,""]}function Ue(n){return[`**${n}**`,"| ID | Time | T | Title | Read | Work |","|----|------|---|-------|------|------|"]}function xe(n,e,t){let s=n.title||"Untitled",r=O.getInstance().getTypeIcon(n.type),{readTokens:o,discoveryDisplay:i}=I(n,t),d=t.showReadTokens?`~${o}`:"",a=t.showWorkTokens?i:"";return`| #${n.id} | ${e||'"'} | ${r} | ${s} | ${d} | ${a} |`}function ke(n,e,t,s){let r=[],o=n.title||"Untitled",i=O.getInstance().getTypeIcon(n.type),{readTokens:d,discoveryDisplay:a}=I(n,s);r.push(`**#${n.id}** ${e||'"'} ${i} **${o}**`),t&&(r.push(""),r.push(t),r.push(""));let p=[];return s.showReadTokens&&p.push(`Read: ~${d}`),s.showWorkTokens&&p.push(`Work: ${a}`),p.length>0&&r.push(p.join(", ")),r.push(""),r}function $e(n,e){let t=`${n.request||"Session started"} (${e})`;return[`**#S${n.id}** ${t}`,""]}function U(n,e){return e?[`**${n}**: ${e}`,""]:[]}function we(n){return n.assistantMessage?["","---","","**Previously**","",`A: ${n.assistantMessage}`,""]:[]}function Fe(n,e){return["",`Access ${Math.round(n/1e3)}k tokens of past research & decisions for just ${e.toLocaleString()}t. Use MCP search tools to access memories by ID.`]}function Pe(n){return`# [${n}] recent context, ${Ne()}

No previous sessions found for this project yet.`}function je(){let n=new Date,e=n.toLocaleDateString("en-CA"),t=n.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit",hour12:!0}).toLowerCase().replace(" ",""),s=n.toLocaleTimeString("en-US",{timeZoneName:"short"}).split(" ").pop();return`${e} ${t} ${s}`}function Xe(n){return["",`${c.bright}${c.cyan}[${n}] recent context, ${je()}${c.reset}`,`${c.gray}${"\u2500".repeat(60)}${c.reset}`,""]}function Be(){let e=O.getInstance().getActiveMode().observation_types.map(t=>`${t.emoji} ${t.id}`).join(" | ");return[`${c.dim}Legend: session-request | ${e}${c.reset}`,""]}function He(){return[`${c.bright}Column Key${c.reset}`,`${c.dim}  Read: Tokens to read this observation (cost to learn it now)${c.reset}`,`${c.dim}  Work: Tokens spent on work that produced this record ( research, building, deciding)${c.reset}`,""]}function We(){return[`${c.dim}Context Index: This semantic index (titles, types, files, tokens) is usually sufficient to understand past work.${c.reset}`,"",`${c.dim}When you need implementation details, rationale, or debugging context:${c.reset}`,`${c.dim}  - Use MCP tools (search, get_observations) to fetch full observations on-demand${c.reset}`,`${c.dim}  - Critical types ( bugfix, decision) often need detailed fetching${c.reset}`,`${c.dim}  - Trust this index over re-reading code for past decisions and learnings${c.reset}`,""]}function Ge(n,e){let t=[];if(t.push(`${c.bright}${c.cyan}Context Economics${c.reset}`),t.push(`${c.dim}  Loading: ${n.totalObservations} observations (${n.totalReadTokens.toLocaleString()} tokens to read)${c.reset}`),t.push(`${c.dim}  Work investment: ${n.totalDiscoveryTokens.toLocaleString()} tokens spent on research, building, and decisions${c.reset}`),n.totalDiscoveryTokens>0&&(e.showSavingsAmount||e.showSavingsPercent)){let s="  Your savings: ";e.showSavingsAmount&&e.showSavingsPercent?s+=`${n.savings.toLocaleString()} tokens (${n.savingsPercent}% reduction from reuse)`:e.showSavingsAmount?s+=`${n.savings.toLocaleString()} tokens`:s+=`${n.savingsPercent}% reduction from reuse`,t.push(`${c.green}${s}${c.reset}`)}return t.push(""),t}function Ye(n){return[`${c.bright}${c.cyan}${n}${c.reset}`,""]}function Ve(n){return[`${c.dim}${n}${c.reset}`]}function Ke(n,e,t,s){let r=n.title||"Untitled",o=O.getInstance().getTypeIcon(n.type),{readTokens:i,discoveryTokens:d,workEmoji:a}=I(n,s),p=t?`${c.dim}${e}${c.reset}`:" ".repeat(e.length),m=s.showReadTokens&&i>0?`${c.dim}(~${i}t)${c.reset}`:"",l=s.showWorkTokens&&d>0?`${c.dim}(${a} ${d.toLocaleString()}t)${c.reset}`:"";return`  ${c.dim}#${n.id}${c.reset}  ${p}  ${o}  ${r} ${m} ${l}`}function qe(n,e,t,s,r){let o=[],i=n.title||"Untitled",d=O.getInstance().getTypeIcon(n.type),{readTokens:a,discoveryTokens:p,workEmoji:m}=I(n,r),l=t?`${c.dim}${e}${c.reset}`:" ".repeat(e.length),g=r.showReadTokens&&a>0?`${c.dim}(~${a}t)${c.reset}`:"",E=r.showWorkTokens&&p>0?`${c.dim}(${m} ${p.toLocaleString()}t)${c.reset}`:"";return o.push(`  ${c.dim}#${n.id}${c.reset}  ${l}  ${d}  ${c.bright}${i}${c.reset}`),s&&o.push(`    ${c.dim}${s}${c.reset}`),(g||E)&&o.push(`    ${g} ${E}`),o.push(""),o}function Je(n,e){let t=`${n.request||"Session started"} (${e})`;return[`${c.yellow}#S${n.id}${c.reset} ${t}`,""]}function x(n,e,t){return e?[`${t}${n}:${c.reset} ${e}`,""]:[]}function ze(n){return n.assistantMessage?["","---","",`${c.bright}${c.magenta}Previously${c.reset}`,"",`${c.dim}A: ${n.assistantMessage}${c.reset}`,""]:[]}function Qe(n,e){let t=Math.round(n/1e3);return["",`${c.dim}Access ${t}k tokens of past research & decisions for just ${e.toLocaleString()}t. Use MCP search tools to access memories by ID.${c.reset}`]}function Ze(n){return`
${c.bright}${c.cyan}[${n}] recent context, ${je()}${c.reset}
${c.gray}${"\u2500".repeat(60)}${c.reset}

${c.dim}No previous sessions found for this project yet.${c.reset}
`}function et(n,e,t,s){let r=[];return s?r.push(...Xe(n)):r.push(...Ae(n)),s?r.push(...Be()):r.push(...Ie()),s?r.push(...He()):r.push(...Le()),s?r.push(...We()):r.push(...ye()),j(t)&&(s?r.push(...Ge(e,t)):r.push(...De(e,t))),r}var te=L(require("path"),1);function W(n){if(!n)return[];try{let e=JSON.parse(n);return Array.isArray(e)?e:[]}catch(e){return u.debug("PARSER","Failed to parse JSON array, using empty fallback",{preview:n?.substring(0,50)},e),[]}}function st(n){return new Date(n).toLocaleString("en-US",{month:"short",day:"numeric",hour:"numeric",minute:"2-digit",hour12:!0})}function rt(n){return new Date(n).toLocaleString("en-US",{hour:"numeric",minute:"2-digit",hour12:!0})}function nt(n){return new Date(n).toLocaleString("en-US",{month:"short",day:"numeric",year:"numeric"})}function tt(n,e){return te.default.isAbsolute(n)?te.default.relative(e,n):n}function ot(n,e,t){let s=W(n);if(s.length>0)return tt(s[0],e);if(t){let r=W(t);if(r.length>0)return tt(r[0],e)}return"General"}function It(n){let e=new Map;for(let s of n){let r=s.type==="observation"?s.data.created_at:s.data.displayTime,o=nt(r);e.has(o)||e.set(o,[]),e.get(o).push(s)}let t=Array.from(e.entries()).sort((s,r)=>{let o=new Date(s[0]).getTime(),i=new Date(r[0]).getTime();return o-i});return new Map(t)}function Lt(n,e){return e.fullObservationField==="narrative"?n.narrative:n.facts?W(n.facts).join(`
`):null}function yt(n,e,t,s,r,o){let i=[];o?i.push(...Ye(n)):i.push(...ve(n));let d=null,a="",p=!1;for(let m of e)if(m.type==="summary"){p&&(i.push(""),p=!1,d=null,a="");let l=m.data,g=st(l.displayTime);o?i.push(...Je(l,g)):i.push(...$e(l,g))}else{let l=m.data,g=ot(l.files_modified,r,l.files_read),E=rt(l.created_at),T=E!==a,h=T?E:"";a=E;let _=t.has(l.id);if(g!==d&&(p&&i.push(""),o?i.push(...Ve(g)):i.push(...Ue(g)),d=g,p=!0),_){let S=Lt(l,s);o?i.push(...qe(l,E,T,S,s)):(p&&!o&&(i.push(""),p=!1),i.push(...ke(l,h,S,s)),d=null)}else o?i.push(Ke(l,E,T,s)):i.push(xe(l,h,s))}return p&&i.push(""),i}function it(n,e,t,s,r){let o=[],i=It(n);for(let[d,a]of i)o.push(...yt(d,a,e,t,s,r));return o}function at(n,e,t){return!(!n.showLastSummary||!e||!!!(e.investigated||e.learned||e.completed||e.next_steps)||t&&e.created_at_epoch<=t.created_at_epoch)}function dt(n,e){let t=[];return e?(t.push(...x("Investigated",n.investigated,c.blue)),t.push(...x("Learned",n.learned,c.yellow)),t.push(...x("Completed",n.completed,c.green)),t.push(...x("Next Steps",n.next_steps,c.magenta))):(t.push(...U("Investigated",n.investigated)),t.push(...U("Learned",n.learned)),t.push(...U("Completed",n.completed)),t.push(...U("Next Steps",n.next_steps))),t}function ct(n,e){return e?ze(n):we(n)}function pt(n,e,t){return!j(e)||n.totalDiscoveryTokens<=0||n.savings<=0?[]:t?Qe(n.totalDiscoveryTokens,n.totalReadTokens):Fe(n.totalDiscoveryTokens,n.totalReadTokens)}var Dt=ut.default.join((0,mt.homedir)(),".claude","plugins","marketplaces","customable","plugin",".install-version");function vt(){try{return new F}catch(n){if(n.code==="ERR_DLOPEN_FAILED"){try{(0,lt.unlinkSync)(Dt)}catch(e){u.debug("SYSTEM","Marker file cleanup failed (may not exist)",{},e)}return u.error("SYSTEM","Native module rebuild needed - restart Claude Code to auto-fix"),null}throw n}}function Ut(n,e){return e?Ze(n):Pe(n)}function xt(n,e,t,s,r,o,i){let d=[],a=J(e);d.push(...et(n,a,s,i));let p=t.slice(0,s.sessionCount),m=Re(p,t),l=ee(e,m),g=Me(e,s.fullObservationCount);d.push(...it(l,g,s,r,i));let E=t[0],T=e[0];at(s,E,T)&&d.push(...dt(E,i));let h=Z(e,s,o,r);return d.push(...ct(h,i)),d.push(...pt(a,s,i)),d.join(`
`).trimEnd()}async function se(n,e=!1){let t=V(),s=n?.cwd??process.cwd(),r=ge(s),o=n?.projects||[r],i=vt();if(!i)return"";try{let d=o.length>1?Oe(i,o,t):z(i,r,t),a=o.length>1?Ce(i,o,t):Q(i,r,t);return d.length===0&&a.length===0?Ut(r,e):xt(r,d,a,t,s,n?.session_id,e)}finally{i.close()}}0&&(module.exports={generateContext});
