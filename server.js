const http = require('http');
const fs = require('fs');
const path = require('path');

const SKILLS_DIR = path.join(process.env.HOME, '.hermes', 'skills');
const WWW_DIR = path.join(__dirname, 'android', 'www');
const PORT = 8080;

function getSkills() {
    const skills = [];
    try {
        const dirs = fs.readdirSync(SKILLS_DIR);
        dirs.sort().forEach(name => {
            if (name.startsWith('.')) return;
            const skillPath = path.join(SKILLS_DIR, name);
            if (!fs.statSync(skillPath).isDirectory()) return;
            
            let description = name.replace(/-/g, ' ').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            const skillFile = path.join(skillPath, 'SKILL.md');
            if (fs.existsSync(skillFile)) {
                const content = fs.readFileSync(skillFile, 'utf8').split('\n');
                for (const line of content.slice(0, 5)) {
                    if (line.startsWith('# ')) {
                        description = line.substring(2).trim();
                        break;
                    }
                }
            }
            skills.push({ name, description });
        });
    } catch (e) {}
    return skills;
}

const server = http.createServer((req, res) => {
    if (req.url === '/api/skills') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(getSkills()));
        return;
    }
    
    let filePath = req.url === '/' ? '/index.html' : req.url;
    filePath = path.join(WWW_DIR, filePath);
    
    // Security: prevent directory traversal
    if (!filePath.startsWith(WWW_DIR)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
    }
    
    const ext = path.extname(filePath);
    const contentTypes = {
        '.html': 'text/html',
        '.js': 'application/javascript',
        '.css': 'text/css',
        '.json': 'application/json'
    };
    
    fs.readFile(filePath, (err, data) => {
        if (err) {
            res.writeHead(404);
            res.end('Not Found');
            return;
        }
        res.writeHead(200, { 'Content-Type': contentTypes[ext] || 'text/plain' });
        res.end(data);
    });
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on http://0.0.0.0:${PORT}`);
});
