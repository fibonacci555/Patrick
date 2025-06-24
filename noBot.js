const axios = require('axios');
const cloudscraper = require('cloudscraper');
const moment = require('moment-timezone');
const fs = require('fs-extra');
const path = require('path');
const logUpdate = require('log-update');
const { URL } = require('url'); // Import the URL class

// --- Configuration and Setup ---

const CONFIG_DIR = path.join(__dirname, 'configs');
fs.ensureDirSync(CONFIG_DIR);

const TZ = 'Europe/Lisbon';
const ERROR_LOG_FILE = path.join(__dirname, 'error.log');

// --- Global State ---

let runningConfigs = new Set();
let stopAllRequested = false;
const configsStatus = new Map();
let dashboardInterval;

const USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'
];

// --- Helper Functions ---

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function createProgressBar(processed, total, barLength = 20) {
    if (total === 0) {
        return `|${'─'.repeat(barLength)}|`;
    }
    const ratio = processed / total;
    const filledChars = Math.round(barLength * ratio);
    const pendingChars = Math.max(0, barLength - filledChars);

    const filledBar = '█'.repeat(filledChars);
    const pendingBar = '─'.repeat(pendingChars);

    return `|${filledBar}${pendingBar}|`;
}

function logError(configId, message) {
    const timestamp = moment().tz(TZ).format('YYYY-MM-DD HH:mm:ss');
    const logMessage = `[${timestamp}] [Config: ${configId}] ${message}\n`;
    fs.appendFileSync(ERROR_LOG_FILE, logMessage);
}

// --- Config Management ---
function loadConfigs() {
    const configs = [];
    const files = fs.readdirSync(CONFIG_DIR).filter(file => file.endsWith('.json'));
    for (const file of files) {
        try {
            const config = fs.readJsonSync(path.join(CONFIG_DIR, file));
            configs.push(config);
        } catch (error) { console.error(`Error loading config file: ${file}`, error); }
    }
    return configs;
}
function saveConfig(config) {
    const configId = config.config_id || Date.now().toString();
    config.config_id = configId;
    fs.writeJsonSync(path.join(CONFIG_DIR, `${configId}.json`), config, { spaces: 2 });
    return configId;
}
function deleteConfig(configId) {
    const configPath = path.join(CONFIG_DIR, `${configId}.json`);
    if (fs.existsSync(configPath)) {
        fs.removeSync(configPath);
        return true;
    }
    return false;
}


// --- Dynamic Dashboard Rendering ---

function renderDashboard() {
    let output = 'Wethrift API Sender\n\n';
    output += `Active Configs: ${runningConfigs.size} | Time: ${moment().tz(TZ).format('HH:mm:ss')}\n`;
    output += '-'.repeat(90) + '\n';
    if (configsStatus.size === 0) {
        output += 'No configurations are currently running.\n';
    } else {
        for (const [id, status] of configsStatus.entries()) {
            const processed = status.successful + status.failed;
            const progressbar = createProgressBar(processed, status.total);
            const progressText = `${processed}/${status.total}`.padEnd(7);
            const successText = `Success: ${status.successful}`.padEnd(12);

        
            
            let line1 = `▶ ID: ${id.padEnd(15)} | ${progressbar} ${progressText} | ${successText} | Status: ${status.status.padEnd(10)} | URL: ${status.url}`;
            
            if (status.status === 'Waiting') {
                const countdown = Math.max(0, Math.round((status.nextRunEndTime - Date.now()) / 1000));
                line1 += `| Next run in: ${countdown}s`;
            }
            
            output += line1 + '\n';
        }
    }
    output += '-'.repeat(90) + '\n';
    if (stopAllRequested) {
        output += 'Stopping all configurations... please wait.\n';
    }
    logUpdate(output);
}


// --- Main Script Function ---

async function runScript(config) {
    const { config_id, base_url, slug, min_sleep, max_sleep, deals } = config;
    const baseUrl = base_url || 'https://www.wethrift.com/api/submit-action';
    const slugName = slug || 'scraper';
    const minSleep = min_sleep || 300;
    const maxSleep = max_sleep || 1000;
    
    // CORRECTED: Dynamically construct the display URL from the base_url and slug
    let storeUrl = 'N/A';
    if (slug) {
        try {
            const origin = new URL(baseUrl).origin;
            storeUrl = `${origin}/${slug}`;
        } catch (e) {
            storeUrl = 'Invalid base_url in config';
        }
    }

    const paramsList = [];
    for (let dealPosition = 1; dealPosition <= 10; dealPosition++) {
        for (const deal of deals) {
            paramsList.push(
                { slug: slugName, deal_id: deal.deal_id, type: 'used', value: '1', deal_position: dealPosition.toString(), deal_code: deal.deal_code },
                { slug: slugName, deal_id: deal.deal_id, type: 'code_working', value: 'yes', deal_position: dealPosition.toString(), deal_code: deal.deal_code }
            );
        }
    }

    configsStatus.set(config_id, {
        id: config_id, status: 'Starting...', total: paramsList.length,
        successful: 0, failed: 0, nextRunEndTime: 0, url: storeUrl,
    });

    while (runningConfigs.has(config_id) && !stopAllRequested) {
        const status = configsStatus.get(config_id);
        status.status = 'Running';
        status.successful = 0;
        status.failed = 0;
        
        const currentUserAgent = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];

        for (const params of paramsList) {
            if (!runningConfigs.has(config_id) || stopAllRequested) break;
            params.t = Math.floor(Date.now()).toString();

            try {
                const response = await cloudscraper({
                    method: 'POST', url: baseUrl, qs: params,
                    headers: { 'User-Agent': currentUserAgent, 'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-US,en;q=0.9', 'Referer': 'https://www.wethrift.com/', 'Origin': 'https://www.wethrift.com', 'X-Requested-With': 'XMLHttpRequest', 'Connection': 'keep-alive' },
                    jar: true, challengesToSolve: 10, resolveWithFullResponse: true, timeout: 15000,
                });

                if (response.statusCode === 200 && JSON.parse(response.body).success) {
                    status.successful++;
                } else {
                    status.failed++;
                }
            } catch (error) {
                status.failed++;
                logError(config_id, `Request failed: ${error.message}`);
            }
            await sleep(2000);
        }

        if (!runningConfigs.has(config_id) || stopAllRequested) break;

        const sleepTime = (Math.random() * (maxSleep - minSleep) + minSleep) * 1000;
        status.status = 'Waiting';
        status.nextRunEndTime = Date.now() + sleepTime;
        await sleep(sleepTime);
    }

    const finalStatus = configsStatus.get(config_id);
    if (finalStatus) {
        finalStatus.status = stopAllRequested ? 'Stopped' : 'Finished';
    }
    runningConfigs.delete(config_id);
}

// --- Main Execution & Process Handlers ---

async function main() {
    console.log('Loading configurations...');
    const configs = loadConfigs();
    if (configs.length === 0) {
        console.log('No configurations found in the "configs" directory.');
        return;
    }
    dashboardInterval = setInterval(renderDashboard, 200);
    const promises = configs.map(config => {
        runningConfigs.add(config.config_id);
        
        // CORRECTED: Dynamically construct the display URL for the "Queued" status
        let storeUrl = 'N/A';
        if (config.slug) {
            try {
                const baseUrl = config.base_url || 'https://www.wethrift.com/api/submit-action';
                const origin = new URL(baseUrl).origin;
                storeUrl = `${origin}/${config.slug}`;
            } catch (e) {
                storeUrl = 'Invalid base_url in config';
            }
        }
        
        configsStatus.set(config.config_id, {
            id: config.config_id, status: 'Queued', total: 0,
            successful: 0, failed: 0, nextRunEndTime: 0, url: storeUrl
        });
        return runScript(config);
    });
    await Promise.all(promises);
    clearInterval(dashboardInterval);
    renderDashboard();
    console.log('\nAll configurations have finished or been stopped.');
}

process.on('uncaughtException', (err, origin) => {
    const timestamp = moment().tz(TZ).format('YYYY-MM-DD HH:mm:ss');
    const logMessage = `[${timestamp}] [FATAL] Uncaught Exception: ${err.message}\nOrigin: ${origin}\nStack: ${err.stack}\n`;
    fs.appendFileSync(ERROR_LOG_FILE, logMessage);
    console.error('\n[FATAL] A critical uncaught error occurred. Logged to error.log. The script will attempt to continue.');
});

main().catch(error => {
    console.error("\nA critical error occurred in the main process:", error);
    clearInterval(dashboardInterval);
});

process.on('SIGINT', () => {
    console.log('\n\nGraceful shutdown requested. Stopping all configs...');
    stopAllRequested = true;
});