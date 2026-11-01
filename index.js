const { Telegraf } = require('telegraf');

// Initialize bot with your Telegram Bot Token
const bot = new Telegraf(process.env.BOT_TOKEN || 'YOUR_BOT_TOKEN_HERE');

const authorizedAdmins = ['6362050635'];

// Check if user has active time-based access
async function checkUserAccess(userId) {
    if (authorizedAdmins.includes(userId.toString())) return true;
    try {
        const record = await db.operation.findOne('access', { userId: userId.toString() });
        if (record && record.expiresAt > Date.now()) {
            return true;
        }
    } catch(e) {}
    return false;
}

// Real API Fetch for WinGo History
async function fetchWingoHistory() {
    try {
        const response = await fetch("https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json?pageNo=1&pageSize=10", {
            headers: {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://ar-lottery01.com/"
            }
        });
        
        if (!response.ok) return [];

        const data = await response.json();
        const list = data.data?.list || data.list;
        if (list && list.length > 0) {
            return list;
        }
    } catch (e) {}
    return [];
}

// 2738 ÷ Past 6 Results Ratio Algorithm
async function calculate2738Engine() {
    const history = await fetchWingoHistory();
    if (!history || history.length < 6) return null;

    try {
        const pastNums = history.slice(0, 6).map(item => parseInt(item.number || 0));
        const divisor = parseInt(pastNums.join('')) || 1;
        
        const ratio = 2738 / divisor;
        const ratioStr = ratio.toFixed(12).replace('.', '');

        let smallCount = 0; // 0 - 4
        let bigCount = 0;   // 5 - 9

        for (let char of ratioStr) {
            const digit = parseInt(char);
            if (!isNaN(digit)) {
                if (digit <= 4) smallCount++;
                else bigCount++;
            }
        }

        const period = parseInt(history[0].issueNumber || 0) + 1;
        const size = bigCount >= smallCount ? "BIG 🟢 [ 5 - 9 ]" : "SMALL 🔵 [ 0 - 4 ]";
        const hotNum = bigCount >= smallCount ? 7 : 2;

        return { period, size, hotNum, pastNums };
    } catch (e) {
        return null;
    }
}

async function sendPredictionMessage(ctx) {
    const userId = ctx.from.id;
    
    const hasAccess = await checkUserAccess(userId);
    if (!hasAccess) {
        return ctx.replyWithMarkdown(
            `❌ *Access Denied!*\n\nYou do not have active VIP access to use this bot.\nYour Telegram ID: \`${userId}\`\n\n_Please send this ID to the admin to get access._`
        );
    }

    const engineData = await calculate2738Engine();
    if (!engineData) {
        return ctx.reply("Failed to fetch live WinGo API data. Please try again.");
    }

    const messageText = `━━━━━━━━━━━━━━\n` +
        `<b>1 MINUTE WINGO [2738 RATIO ENGINE]</b>\n\n` +
        `👀 <b>Ongoing Period:</b> <code>${engineData.period}</code>\n` +
        `❤️‍🔥 <b>Prediction:</b> ${engineData.size}\n` +
        `🎲 <b>Suggested Number:</b> ${engineData.hotNum}\n` +
        `📊 <b>Past 6 Results:</b> ${engineData.pastNums.join(', ')}\n\n` +
        `━━━━━━━━━━━━━━`;

    const keyboard = {
        inline_keyboard: [[{ text: "🔄 Get Next Prediction", callback_data: "get_prediction" }]]
    };

    await ctx.reply(messageText, {
        parse_mode: "HTML",
        reply_markup: keyboard
    });
}

bot.command('start', async (ctx) => {
    const userId = ctx.from.id;
    try {
        const userExists = await db.operation.findOne('usersd', { id: userId });
        if (!userExists) {
            await db.operation.insertOne('usersd', { id: userId, joinedAt: new Date() }, { upsert: true });
        }
    } catch(e){}

    await sendPredictionMessage(ctx);
});

bot.action('get_prediction', async (ctx) => {
    await sendPredictionMessage(ctx);
});

bot.command('admin', async (ctx) => {
    if (!authorizedAdmins.includes(ctx.from.id.toString())) return;
    await ctx.replyWithMarkdown(
        `⚙️ *Admin Access Panel*\n\n` +
        `To grant access to a user, use the command:\n` +
        `\`/grant <userId> <days>\`\n\n` +
        `Example: \`/grant 123456789 30\` (Grants 30 days access)`
    );
});

bot.command('grant', async (ctx) => {
    if (!authorizedAdmins.includes(ctx.from.id.toString())) return;
    
    const args = ctx.message.text.split(' ');
    if (args.length < 3) {
        return ctx.replyWithMarkdown(`⚠️ *Usage:* \`/grant <userId> <days>\``);
    }

    const targetUserId = args[1];
    const days = parseInt(args[2]);
    const expiresAt = Date.now() + (days * 24 * 60 * 60 * 1000);

    try {
        await db.operation.updateOne(
            'access',
            { userId: targetUserId },
            { $set: { userId: targetUserId, expiresAt, grantedAt: Date.now() } },
            { upsert: true }
        );
        await ctx.replyWithMarkdown(`✅ Successfully granted *${days} days* access to user ID: \`${targetUserId}\``);
        
        try {
            await bot.telegram.sendMessage(targetUserId, `🎉 *Your VIP Access has been granted for ${days} days!* Send /start to get predictions.`);
        } catch(e) {}
    } catch(e) {
        await ctx.reply("Failed to grant access.");
    }
});

bot.launch().then(() => {
    console.log("🤖 WinGo 2738 Engine Bot with Time-Based Access is running!");
}).catch((err) => {
    console.error("Bot launch error:", err);
});

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
            
