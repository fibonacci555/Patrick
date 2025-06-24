const TelegramBot = require('node-telegram-bot-api');
const axios = require('axios');
const cloudscraper = require('cloudscraper');
const moment = require('moment-timezone');
const fs = require('fs-extra');
const path = require('path');

// Bot token
const TOKEN = '7681224927:AAE96XaKmmRA8gJApv0kFxos6f36Js_4S7s';
const bot = new TelegramBot(TOKEN, { polling: true });

// Configs directory
const CONFIG_DIR = path.join(__dirname, 'configs');
fs.ensureDirSync(CONFIG_DIR);

// Global state
let runningConfigs = new Set(); // Track running config IDs
let stopAllRequested = false; // Flag to stop all configs

// Timezone
const TZ = 'Europe/Lisbon';

// Load existing configs
function loadConfigs() {
  const configs = [];
  const files = fs.readdirSync(CONFIG_DIR).filter(file => file.endsWith('.json'));
  for (const file of files) {
    const config = fs.readJsonSync(path.join(CONFIG_DIR, file));
    configs.push(config);
  }
  return configs;
}

// Save config to JSON
function saveConfig(config) {
  const configId = config.config_id || Date.now().toString();
  config.config_id = configId;
  fs.writeJsonSync(path.join(CONFIG_DIR, `${configId}.json`), config, { spaces: 2 });
  return configId;
}

// Delete config
function deleteConfig(configId) {
  const configPath = path.join(CONFIG_DIR, `${configId}.json`);
  if (fs.existsSync(configPath)) {
    fs.removeSync(configPath);
    return true;
  }
  return false;
}

// Sleep function
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

// Truncate message for Telegram
function truncateMessage(message, maxLength = 4000) {
  if (message.length <= maxLength) return message;
  return message.slice(0, maxLength - 3) + '...';
}

// Main script function
async function runScript(config, chatId) {
  const baseUrl = config.base_url || 'https://www.wethrift.com/api/submit-action';
  const slug = config.slug || 'dropship';
  const minSleep = config.min_sleep || 300;
  const maxSleep = config.max_sleep || 1000;
  const paramsList = [];
  const positionStatus = new Map(); // Track status by deal_position
  let consecutive403s = 0;
  const MAX_403S = 3; // Stop after 3 consecutive 403s

  // Initialize position status and build params for deal_positions 1-10
  for (let dealPosition = 1; dealPosition <= 10; dealPosition++) {
    positionStatus.set(dealPosition.toString(), { total: 0, successful: 0 });
    for (const deal of config.deals) {
      const dealId = deal.deal_id;
      const dealCode = deal.deal_code;
      positionStatus.get(dealPosition.toString()).total += 2; // Two requests per deal
      paramsList.push(
        { slug, deal_id: dealId, type: 'used', value: '1', deal_position: dealPosition.toString(), deal_code: dealCode, _deal_position: dealPosition.toString() },
        { slug, deal_id: dealId, type: 'code_working', value: 'yes', deal_position: dealPosition.toString(), deal_code: dealCode, _deal_position: dealPosition.toString() }
      );
    }
  }

  while (runningConfigs.has(config.config_id) && !stopAllRequested) {
    console.log(`[INFO] Sending API actions for config ${config.config_id}...`);
    let hasError = false;

    // Reset successful counts for this loop
    for (const [position] of positionStatus) {
      positionStatus.get(position).successful = 0;
    }

    for (const params of paramsList) {
      if (!runningConfigs.has(config.config_id) || stopAllRequested) break;
      params.t = Math.floor(Date.now()).toString();
      const timestamp = moment().tz(TZ).format('YYYY-MM-DD HH:mm:ss');
      console.log(`[INFO] Request sent at ${timestamp} for config ${config.config_id}, deal_position=${params._deal_position}, type=${params.type}`);
      try {
        const response = await cloudscraper({
          method: 'POST',
          url: baseUrl,
          qs: params,
          headers: {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.wethrift.com/',
            'Origin': 'https://www.wethrift.com',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
          },
          jar: true, // Enable cookies
          challengesToSolve: 5, // Increase attempts to solve Cloudflare challenges
          resolveWithFullResponse: true, // Get full response object
        });
        console.log(`Status Code: ${response.statusCode}`);
        console.log(`Response: ${response.body}`);
        console.log('---');
        if (response.statusCode === 200 && JSON.parse(response.body).success) {
          positionStatus.get(params._deal_position).successful++;
        }
        consecutive403s = 0; // Reset counter on success
      } catch (error) {
        hasError = true;
        console.error(`[ERROR] Request failed: ${error.message}`);
        let errorMessage = `[ERROR] Request failed for config ${config.config_id}, deal_position=${params._deal_position}, type=${params.type}: ${error.message}\n`;
        if (error.response) {
          console.error(`Status Code: ${error.response.statusCode}`);
          console.error(`Response Body: ${error.response.body}`);
          console.error(`Headers: ${JSON.stringify(error.response.headers, null, 2)}`);
          errorMessage += `Status: ${error.response.statusCode}\nBody: ${truncateMessage(error.response.body, 1000)}\n`;
          if (error.response.statusCode === 403) {
            consecutive403s++;
            errorMessage += `Consecutive 403s: ${consecutive403s}/${MAX_403S}\n`;
            if (consecutive403s >= MAX_403S) {
              runningConfigs.delete(config.config_id);
              errorMessage += `Stopped config ${config.config_id} due to too many 403 errors. Check Cloudflare protection or deal parameters.`;
              await bot.sendMessage(config.chat_id || chatId, truncateMessage(errorMessage));
              return { success: false, error: config.config_id };
            }
          }
        } else if (error.request) {
          console.error(`Request Details: ${JSON.stringify(error.request, null, 2)}`);
          errorMessage += `Request failed without response.\n`;
        }
        console.error(`Stack: ${error.stack}`);
      }
      await sleep(2000); // 2 seconds between requests
    }

    // Send Telegram summary message
    if (runningConfigs.has(config.config_id) && !stopAllRequested) {
      let summaryMessage = `Request results for config ${config.config_id}:\n`;
      for (const [position, status] of positionStatus) {
        summaryMessage += `${status.successful}/${status.total} requests for position ${position} worked\n`;
      }
      try {
        await bot.sendMessage(config.chat_id || chatId, truncateMessage(summaryMessage));
      } catch (telegramError) {
        console.error(`[ERROR] Failed to send Telegram message: ${telegramError.message}`);
      }
    }

    if (!runningConfigs.has(config.config_id) || stopAllRequested) {
      return { success: !hasError, error: hasError ? config.config_id : null };
    }
    const sleepTime = Math.random() * (maxSleep - minSleep) + minSleep;
    console.log(`[INFO] Waiting for ${Math.round(sleepTime)} seconds for config ${config.config_id}...\n`);
    await sleep(sleepTime * 1000);
  }
  return { success: !hasError, error: hasError ? config.config_id : null };
}

// Start command
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  bot.sendMessage(chatId, 
    'Welcome to the Script Management Bot!\n' +
    'Available commands:\n' +
    '/add - Add a new configuration\n' +
    '/list - List all configurations\n' +
    '/delete <config_id> - Delete a configuration\n' +
    '/run <config_id | all> - Run a configuration or all configurations\n' +
    '/stop <config_id | all> - Stop a configuration or all configurations\n' +
    '/settime <config_id> <min_sleep> <max_sleep> - Set sleep time range'
  );
});

// Add new config
bot.onText(/\/add/, (msg) => {
  const chatId = msg.chat.id;
  bot.sendMessage(chatId, 
    'Send the configuration in JSON format:\n' +
    '{\n' +
    '  "slug": "dropship",\n' +
    '  "base_url": "https://www.wethrift.com/api/submit-action",\n' +
    '  "min_sleep": 300,\n' +
    '  "max_sleep": 1000,\n' +
    '  "deals": [\n' +
    '    {"deal_id": "P3P5D9X5JJ", "deal_code": "SAVE25", "deal_position": "1"},\n' +
    '    {"deal_id": "P3P5D9X5JJ", "deal_code": "SAVE25", "deal_position": "2"}\n' +
    '  ]\n' +
    '}'
  );
  bot.once('message', (nextMsg) => {
    if (nextMsg.chat.id !== chatId) return;
    try {
      const config = JSON.parse(nextMsg.text);
      if (!config.deals) throw new Error("Field 'deals' is required");
      for (const deal of config.deals) {
        if (!deal.deal_id || !deal.deal_code || !deal.deal_position) {
          throw new Error("Each deal must have 'deal_id', 'deal_code', and 'deal_position'");
        }
      }
      config.chat_id = chatId; // Store chat_id for error notifications
      const configId = saveConfig(config);
      bot.sendMessage(chatId, `Configuration saved with ID: ${configId}`);
    } catch (error) {
      bot.sendMessage(chatId, `Error: ${error.message}`);
    }
  });
});

// List configs
bot.onText(/\/list/, (msg) => {
  const chatId = msg.chat.id;
  const configs = loadConfigs();
  if (!configs.length) {
    bot.sendMessage(chatId, 'No configurations found.');
    return;
  }
  let response = 'Available configurations:\n';
  for (const config of configs) {
    response += `ID: ${config.config_id}\n`;
    response += `Deals: ${config.deals.length}\n`;
    response += `Min Sleep: ${config.min_sleep || 300}s\n`;
    response += `Max Sleep: ${config.max_sleep || 1000}s\n`;
    response += '---\n';
  }
  bot.sendMessage(chatId, response);
});

// Delete config
bot.onText(/\/delete (.+)/, (msg, match) => {
  const chatId = msg.chat.id;
  const configId = match[1];
  if (deleteConfig(configId)) {
    bot.sendMessage(chatId, `Configuration ${configId} deleted.`);
  } else {
    bot.sendMessage(chatId, `Configuration ${configId} not found.`);
  }
});

// Run config
bot.onText(/\/run (.+)/, async (msg, match) => {
  const chatId = msg.chat.id;
  const configId = match[1];

  if (configId === 'all') {
    const configs = loadConfigs();
    if (!configs.length) {
      bot.sendMessage(chatId, 'No configurations found.');
      return;
    }
    if (runningConfigs.size > 0) {
      bot.sendMessage(chatId, 'One or more configs are already running. Use /stop to stop them.');
      return;
    }
    bot.sendMessage(chatId, `Starting configs for all (${configs.length} configs).`);
    while (!stopAllRequested) {
      let successful = 0;
      let errors = 0;
      const errorConfigIds = [];
      const promises = configs.map(config => {
        if (runningConfigs.has(config.config_id)) return Promise.resolve({ success: false, error: config.config_id });
        config.chat_id = chatId; // Store chat_id for notifications
        runningConfigs.add(config.config_id);
        return runScript(config, chatId).catch(error => {
          console.error(`[ERROR] Script error for config ${config.config_id}: ${error.message}`);
          return { success: false, error: config.config_id };
        }).finally(() => {
          runningConfigs.delete(config.config_id);
        });
      });
      const results = await Promise.all(promises);
      results.forEach(result => {
        if (result.success) successful++;
        else {
          errors++;
          if (result.error) errorConfigIds.push(result.error);
        }
      });
      if (stopAllRequested) break;
      const summaryMessage = `Summary: Success for ${successful}/${configs.length} configs, errors = ${errors};${errorConfigIds.join(',') || 'none'}`;
      try {
        await bot.sendMessage(chatId, truncateMessage(summaryMessage));
      } catch (telegramError) {
        console.error(`[ERROR] Failed to send Telegram summary: ${telegramError.message}`);
      }
      const globalSleep = Math.random() * (1000 - 300) + 300; // Global sleep between 300-1000s
      console.log(`[INFO] Waiting for ${Math.round(globalSleep)} seconds before next iteration...`);
      await sleep(globalSleep * 1000);
    }
    return;
  }

  const configPath = path.join(CONFIG_DIR, `${configId}.json`);
  if (!fs.existsSync(configPath)) {
    bot.sendMessage(chatId, `Configuration ${configId} not found.`);
    return;
  }
  if (runningConfigs.has(configId)) {
    bot.sendMessage(chatId, `Configuration ${configId} is already running.`);
    return;
  }
  const config = fs.readJsonSync(configPath);
  config.chat_id = chatId; // Store chat_id for error notifications
  runningConfigs.add(config.config_id);
  bot.sendMessage(chatId, `Running configuration ${configId}.`);
  runScript(config, chatId).catch(error => {
    console.error(`[ERROR] Script error: ${error.message}`);
    runningConfigs.delete(config.config_id);
    bot.sendMessage(chatId, `Script stopped due to error: ${error.message}`);
  }).finally(() => {
    runningConfigs.delete(config.config_id);
  });
});

// Stop script
bot.onText(/\/stop (.+)/, (msg, match) => {
  const chatId = msg.chat.id;
  const configId = match[1];

  if (configId === 'all') {
    if (runningConfigs.size === 0) {
      bot.sendMessage(chatId, 'No configs are running.');
      return;
    }
    stopAllRequested = true;
    runningConfigs.clear();
    bot.sendMessage(chatId, 'Stopped all configs.');
    stopAllRequested = false; // Reset flag
    return;
  }

  const configPath = path.join(CONFIG_DIR, `${configId}.json`);
  if (!fs.existsSync(configPath)) {
    bot.sendMessage(chatId, `Configuration ${configId} not found.`);
    return;
  }
  if (!runningConfigs.has(configId)) {
    bot.sendMessage(chatId, `Configuration ${configId} is not running.`);
    return;
  }
  runningConfigs.delete(configId);
  bot.sendMessage(chatId, `Script for configuration ${configId} stopped.`);
});

// Set sleep time
bot.onText(/\/settime (.+) (.+) (.+)/, (msg, match) => {
  const chatId = msg.chat.id;
  const [configId, minSleep, maxSleep] = match.slice(1);
  const configPath = path.join(CONFIG_DIR, `${configId}.json`);
  if (!fs.existsSync(configPath)) {
    bot.sendMessage(chatId, `Configuration ${configId} not found.`);
    return;
  }
  try {
    const min = parseFloat(minSleep);
    const max = parseFloat(maxSleep);
    if (min < 0 || max < min) {
      throw new Error('Invalid values for min_sleep or max_sleep');
    }
    const config = fs.readJsonSync(configPath);
    config.min_sleep = min;
    config.max_sleep = max;
    saveConfig(config);
    bot.sendMessage(chatId, `Sleep time updated for configuration ${configId}: min_sleep=${min}s, max_sleep=${max}s`);
  } catch (error) {
    bot.sendMessage(chatId, `Error: ${error.message}`);
  }
});

console.log('Bot is running...');