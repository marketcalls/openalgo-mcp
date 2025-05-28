// Enhanced OpenAlgo Trading Assistant JavaScript - Streaming Fix

class TradingAssistant {
    constructor() {
        this.socket = null;
        this.clientId = null;
        this.isConnected = false;
        this.chatHistory = [];
        this.currentTheme = 'synthwave';
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.messageQueue = [];
        this.isTyping = false;
        this.currentAssistantMessageId = null; // Track current streaming message
        this.messageIdCounter = 0; // Counter for unique message IDs
        this.isStreaming = false; // Track if we're currently streaming
        
        this.init();
    }

    init() {
        // Generate unique client ID
        this.clientId = uuid.v4();
        
        // Initialize event listeners
        this.setupEventListeners();
        
        // Initialize UI components
        this.initializeUI();
        
        // Check server status
        this.checkServerStatus();
        
        // Auto-connect after a delay
        setTimeout(() => {
            this.connectWebSocket();
        }, 1000);
        
        // Set up periodic status checks
        setInterval(() => {
            if (!this.isConnected) {
                this.checkServerStatus();
            }
        }, 30000);
    }

    setupEventListeners() {
        // Message form
        document.getElementById('message-form').addEventListener('submit', (e) => this.sendMessage(e));
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
        
        // Input handling
        const userInput = document.getElementById('user-input');
        userInput.addEventListener('input', (e) => this.handleInputChange(e));
        userInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        
        // Connection toggle
        document.getElementById('connect-btn').addEventListener('click', () => this.toggleConnection());
        
        // Window events
        window.addEventListener('beforeunload', () => this.cleanup());
        window.addEventListener('online', () => this.handleOnline());
        window.addEventListener('offline', () => this.handleOffline());
    }

    initializeUI() {
        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        // Set welcome message timestamp
        const welcomeTime = document.getElementById('welcome-time');
        if (welcomeTime) {
            welcomeTime.textContent = new Date().toLocaleTimeString();
        }
        
        // Initialize theme
        this.setTheme(this.currentTheme);
        
        // Add sample data
        setTimeout(() => {
            this.addSampleChatHistory();
            this.updateMarketOverview();
        }, 2000);
    }

    async checkServerStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            const serverUrl = document.getElementById('server-url');
            if (serverUrl) {
                serverUrl.textContent = data.mcp_server;
            }
            
            if (data.status === 'connected') {
                this.updateConnectionStatus('ready');
            } else {
                this.updateConnectionStatus('disconnected');
                if (data.status === 'error') {
                    this.showNotification(`Server error: ${data.message}`, 'error');
                }
            }
        } catch (error) {
            console.error('Error checking server status:', error);
            this.updateConnectionStatus('disconnected');
            this.showNotification('Could not connect to the server', 'error');
        }
    }

    toggleConnection() {
        if (this.isConnected) {
            this.disconnectWebSocket();
        } else {
            this.connectWebSocket();
        }
    }

    connectWebSocket() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            return;
        }
        
        this.updateConnectionStatus('connecting');
        
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = `${protocol}${window.location.host}/ws/${this.clientId}`;
        
        try {
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('connected');
                this.showNotification('Connected to trading assistant', 'success');
                this.processMessageQueue();
            };
            
            this.socket.onmessage = (event) => {
                this.handleWebSocketMessage(event);
            };
            
            this.socket.onclose = (event) => {
                console.log('WebSocket disconnected', event);
                this.isConnected = false;
                this.updateConnectionStatus('disconnected');
                
                // Attempt reconnection if not intentionally closed
                if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.attemptReconnection();
                }
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('error');
                this.showNotification('Connection error occurred', 'error');
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.updateConnectionStatus('error');
            this.showNotification('Failed to establish connection', 'error');
        }
    }

    disconnectWebSocket() {
        if (this.socket) {
            this.socket.close(1000, 'User initiated disconnect');
            this.socket = null;
        }
        this.isConnected = false;
        this.updateConnectionStatus('disconnected');
    }

    attemptReconnection() {
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
        
        this.showNotification(`Reconnecting in ${delay/1000} seconds... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, 'warning');
        
        setTimeout(() => {
            if (!this.isConnected) {
                this.connectWebSocket();
            }
        }, delay);
    }

    handleWebSocketMessage(event) {
        try {
            const message = JSON.parse(event.data);
            console.log('Received message:', message); // Debug log
            
            if (message.role === 'system') {
                // Only show system messages that are not "Processing your request..."
                if (message.content !== 'Processing your request...') {
                    this.showNotification(message.content, 'info');
                }
                return; // Don't add system messages to chat
            } 
            
            if (message.role === 'assistant') {
                this.removeTypingIndicator();
                
                if (message.partial === true) {
                    // This is a streaming partial response
                    if (!this.isStreaming) {
                        // First streaming chunk - create new message
                        this.isStreaming = true;
                        this.addMessage('assistant', message.content);
                    } else {
                        // Subsequent streaming chunks - append to existing message
                        this.appendToCurrentAssistantMessage(message.content);
                    }
                } else if (message.partial === false) {
                    // This is the end of streaming or a complete non-streaming message
                    if (this.isStreaming) {
                        // End of streaming - reset streaming state but don't add new message
                        console.log('Streaming complete, resetting state');
                        this.isStreaming = false;
                        this.currentAssistantMessageId = null;
                    } else if (message.content && message.content.trim()) {
                        // This is a complete non-streaming message with content
                        this.addMessage('assistant', message.content);
                    }
                    // Ignore empty final messages
                }
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    }

    updateConnectionStatus(status) {
        const indicator = document.getElementById('connection-indicator');
        const statusText = document.getElementById('connection-status');
        const connectBtn = document.getElementById('connect-btn');
        
        if (!indicator || !statusText || !connectBtn) return;
        
        // Remove all status classes
        indicator.className = 'w-3 h-3 rounded-full';
        
        switch (status) {
            case 'connected':
                indicator.classList.add('status-connected');
                statusText.textContent = 'Connected';
                connectBtn.innerHTML = '<i data-lucide="wifi-off" class="w-4 h-4 mr-1"></i>Disconnect';
                connectBtn.className = 'btn btn-sm btn-error floating-action';
                break;
                
            case 'connecting':
                indicator.classList.add('status-connecting');
                statusText.textContent = 'Connecting...';
                connectBtn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 mr-1 animate-spin"></i>Connecting';
                connectBtn.className = 'btn btn-sm btn-warning floating-action';
                break;
                
            case 'ready':
                indicator.classList.add('status-connecting');
                statusText.textContent = 'Ready';
                connectBtn.innerHTML = '<i data-lucide="wifi" class="w-4 h-4 mr-1"></i>Connect';
                connectBtn.className = 'btn btn-sm btn-primary floating-action';
                break;
                
            case 'error':
                indicator.classList.add('status-disconnected');
                statusText.textContent = 'Error';
                connectBtn.innerHTML = '<i data-lucide="alert-circle" class="w-4 h-4 mr-1"></i>Retry';
                connectBtn.className = 'btn btn-sm btn-warning floating-action';
                break;
                
            default:
                indicator.classList.add('status-disconnected');
                statusText.textContent = 'Disconnected';
                connectBtn.innerHTML = '<i data-lucide="wifi" class="w-4 h-4 mr-1"></i>Connect';
                connectBtn.className = 'btn btn-sm btn-accent floating-action';
        }
        
        // Reinitialize icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    sendMessage(event) {
        event.preventDefault();
        
        const inputElement = document.getElementById('user-input');
        const message = inputElement.value.trim();
        
        if (!message) return;
        
        if (!this.isConnected) {
            this.showNotification('Please connect to the server first', 'warning');
            this.messageQueue.push(message);
            return;
        }
        
        // Reset streaming state when user sends new message
        this.isStreaming = false;
        this.currentAssistantMessageId = null;
        
        // Add user message to chat
        this.addMessage('user', message);
        
        // Send message to server
        try {
            this.socket.send(JSON.stringify({
                role: 'user',
                content: message
            }));
        } catch (error) {
            console.error('Error sending message:', error);
            this.showNotification('Failed to send message', 'error');
            return;
        }
        
        // Clear input and add typing indicator
        inputElement.value = '';
        this.resetTextareaHeight(inputElement);
        this.addTypingIndicator();
        
        // Store in history
        this.chatHistory.push({
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        });
    }

    processMessageQueue() {
        while (this.messageQueue.length > 0 && this.isConnected) {
            const message = this.messageQueue.shift();
            document.getElementById('user-input').value = message;
            this.sendMessage({ preventDefault: () => {} });
            
            // Add small delay between queued messages
            if (this.messageQueue.length > 0) {
                setTimeout(() => this.processMessageQueue(), 1000);
                break;
            }
        }
    }

    addMessage(role, content) {
        this.removeTypingIndicator();
        
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;
        
        const messageId = `message-${this.messageIdCounter++}`;
        const chatDiv = document.createElement('div');
        chatDiv.className = `chat ${role === 'user' ? 'chat-end' : 'chat-start'} message-enter`;
        chatDiv.setAttribute('data-message-id', messageId);
        
        const isUser = role === 'user';
        const timestamp = new Date().toLocaleTimeString();
        
        chatDiv.innerHTML = `
            <div class="chat-image avatar">
                <div class="w-10 rounded-full ${isUser ? 'bg-gradient-to-r from-accent to-secondary' : 'bg-gradient-to-r from-primary to-secondary'} flex items-center justify-center">
                    <i data-lucide="${isUser ? 'user' : 'bot'}" class="w-5 h-5 text-white"></i>
                </div>
            </div>
            <div class="chat-header">
                ${isUser ? 'You' : 'Trading Assistant'}
                <time class="text-xs opacity-50">${timestamp}</time>
            </div>
            <div class="chat-bubble ${isUser ? 'chat-bubble-accent' : 'chat-bubble-primary'}">
                ${role === 'assistant' ? this.parseMarkdown(content) : this.escapeHtml(content)}
            </div>
        `;
        
        messagesContainer.appendChild(chatDiv);
        this.scrollToBottom();
        
        // Set current assistant message ID for streaming
        if (role === 'assistant') {
            this.currentAssistantMessageId = messageId;
        }
        
        // Reinitialize icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        // Store in history
        this.chatHistory.push({
            role,
            content,
            timestamp: new Date().toISOString()
        });
    }

    addTypingIndicator() {
        this.removeTypingIndicator();
        this.isTyping = true;
        
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;
        
        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        typingDiv.className = 'chat chat-start';
        
        typingDiv.innerHTML = `
            <div class="chat-image avatar">
                <div class="w-10 rounded-full bg-gradient-to-r from-primary to-secondary flex items-center justify-center">
                    <i data-lucide="bot" class="w-5 h-5 text-white"></i>
                </div>
            </div>
            <div class="chat-bubble chat-bubble-primary">
                <div class="typing-enhanced">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(typingDiv);
        this.scrollToBottom();
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    removeTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
            this.isTyping = false;
        }
    }

    appendToCurrentAssistantMessage(content) {
        if (!this.currentAssistantMessageId) {
            // If no current message, create a new one
            this.addMessage('assistant', content);
            return;
        }
        
        const messagesContainer = document.getElementById('chat-messages');
        const currentMessage = messagesContainer.querySelector(`[data-message-id="${this.currentAssistantMessageId}"]`);
        
        if (!currentMessage) {
            // If message not found, create a new one
            this.addMessage('assistant', content);
            return;
        }
        
        const chatBubble = currentMessage.querySelector('.chat-bubble');
        if (!chatBubble) return;
        
        // Get current content and append new content
        const currentContent = this.extractTextContent(chatBubble.innerHTML);
        const updatedContent = currentContent + content;
        
        // Update the bubble with the new content
        chatBubble.innerHTML = this.parseMarkdown(updatedContent);
        
        this.scrollToBottom();
        
        // Update chat history
        if (this.chatHistory.length > 0) {
            const lastEntry = this.chatHistory[this.chatHistory.length - 1];
            if (lastEntry.role === 'assistant') {
                lastEntry.content += content;
            }
        }
    }

    scrollToBottom() {
        const messagesContainer = document.getElementById('chat-messages');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    parseMarkdown(content) {
        if (typeof marked !== 'undefined') {
            // Configure marked for better table rendering
            marked.setOptions({
                gfm: true,  // GitHub Flavored Markdown
                breaks: true,
                tables: true,
                headerIds: false
            });
            
            // Process table-specific content for better formatting
            let processedContent = content;
            
            // Fix malformed tables from GROQ responses
            if (content.includes('|') && !content.includes('```')) {
                const lines = content.split('\n');
                const tableLines = [];
                let inTable = false;
                
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i].trim();
                    if (line.startsWith('|') && line.endsWith('|')) {
                        if (!inTable) {
                            inTable = true;
                            // If this is first line of table and next line isn't a separator, add one
                            if (i + 1 < lines.length) {
                                const nextLine = lines[i + 1].trim();
                                if (!nextLine.includes('---') && !nextLine.includes('===')) {
                                    // Count columns and create separator
                                    const colCount = (line.match(/\|/g) || []).length - 1;
                                    tableLines.push(line);
                                    tableLines.push('|' + Array(colCount).fill(' --- |').join(''));
                                    continue;
                                }
                            }
                        }
                        tableLines.push(line);
                    } else if (inTable && line.includes('|')) {
                        // Handle malformed table rows that don't start/end with |
                        tableLines.push('|' + line + (line.endsWith('|') ? '' : '|'));
                    } else if (line === '' && inTable) {
                        inTable = false;
                    } else {
                        tableLines.push(line);
                    }
                }
                processedContent = tableLines.join('\n');
            }
            
            return marked.parse(processedContent);
        }
        return this.escapeHtml(content).replace(/\n/g, '<br>');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    extractTextContent(html) {
        const div = document.createElement('div');
        div.innerHTML = html;
        return div.textContent || div.innerText || '';
    }

    // UI Helper Methods
    quickMessage(message) {
        const input = document.getElementById('user-input');
        if (input) {
            input.value = message;
            this.sendMessage({ preventDefault: () => {} });
        }
    }

    startNewChat() {
        this.clientId = uuid.v4();
        this.currentAssistantMessageId = null;
        this.messageIdCounter = 0;
        this.isStreaming = false;
        this.clearChat();
        if (!this.isConnected) {
            this.connectWebSocket();
        }
        this.showNotification('Started new chat session', 'success');
    }

    clearChat() {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;
        
        const timestamp = new Date().toLocaleTimeString();
        messagesContainer.innerHTML = `
            <div class="chat chat-start message-enter">
                <div class="chat-image avatar">
                    <div class="w-10 rounded-full bg-gradient-to-r from-primary to-secondary flex items-center justify-center">
                        <i data-lucide="bot" class="w-5 h-5 text-white"></i>
                    </div>
                </div>
                <div class="chat-header">
                    Trading Assistant
                    <time class="text-xs opacity-50">${timestamp}</time>
                </div>
                <div class="chat-bubble chat-bubble-primary">
                    Chat cleared. Ready for new conversation! 🎉
                </div>
            </div>
        `;
        
        this.chatHistory = [];
        this.currentAssistantMessageId = null;
        this.messageIdCounter = 0;
        this.isStreaming = false;
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    // Event Handlers
    handleKeyboardShortcuts(event) {
        // Ctrl/Cmd + K to focus on input
        if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
            event.preventDefault();
            const input = document.getElementById('user-input');
            if (input) input.focus();
        }
        
        // Ctrl/Cmd + N for new chat
        if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
            event.preventDefault();
            this.startNewChat();
        }
        
        // Ctrl/Cmd + L to clear chat
        if ((event.ctrlKey || event.metaKey) && event.key === 'l') {
            event.preventDefault();
            this.clearChat();
        }
        
        // Escape to clear input
        if (event.key === 'Escape') {
            const input = document.getElementById('user-input');
            if (input) {
                input.value = '';
                this.resetTextareaHeight(input);
            }
        }
    }

    handleKeyDown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage(event);
        }
    }

    handleInputChange(event) {
        this.autoResizeTextarea(event.target);
    }

    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    resetTextareaHeight(textarea) {
        textarea.style.height = 'auto';
    }

    handleOnline() {
        this.showNotification('Connection restored', 'success');
        if (!this.isConnected) {
            this.connectWebSocket();
        }
    }

    handleOffline() {
        this.showNotification('Connection lost - you are offline', 'warning');
    }

    // Notification System
    showNotification(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = 'toast toast-top toast-end z-50';
        
        const alertClass = {
            'success': 'alert-success',
            'error': 'alert-error',
            'warning': 'alert-warning',
            'info': 'alert-info'
        }[type] || 'alert-info';
        
        const iconName = {
            'success': 'check-circle',
            'error': 'x-circle',
            'warning': 'alert-triangle',
            'info': 'info'
        }[type] || 'info';
        
        toast.innerHTML = `
            <div class="alert ${alertClass} toast-modern">
                <i data-lucide="${iconName}" class="w-4 h-4"></i>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        setTimeout(() => {
            toast.remove();
        }, duration);
    }

    // Theme Management
    setTheme(theme) {
        this.currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('trading-assistant-theme', theme);
    }

    toggleTheme() {
        const themes = ['synthwave', 'cyberpunk', 'dark', 'night', 'forest', 'luxury', 'business', 'cupcake'];
        const currentIndex = themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % themes.length;
        const newTheme = themes[nextIndex];
        
        this.setTheme(newTheme);
        this.showNotification(`Switched to ${newTheme} theme`, 'success');
    }

    // Quick Actions
    getPortfolio() {
        this.quickMessage('Show my portfolio and holdings with performance metrics');
    }

    getFunds() {
        this.quickMessage('Show my available funds and margin details');
    }

    getOrders() {
        this.quickMessage('List all my orders with current status');
    }

    // Sample Data
    addSampleChatHistory() {
        const chatHistoryContainer = document.getElementById('chat-history');
        if (!chatHistoryContainer) return;
        
        const sampleChats = [
            { title: 'Portfolio Analysis - Today', time: '2 mins ago' },
            { title: 'NIFTY Options Strategy', time: '1 hour ago' },
            { title: 'Fund Transfer Query', time: '3 hours ago' },
            { title: 'Order Status Check', time: 'Yesterday' }
        ];

        sampleChats.forEach((chat, index) => {
            const chatItem = document.createElement('div');
            chatItem.className = 'btn btn-ghost btn-sm w-full text-left justify-start mb-1 hover:bg-primary/10';
            chatItem.innerHTML = `
                <i data-lucide="message-circle" class="w-4 h-4 mr-2 opacity-60"></i>
                <div class="flex flex-col items-start flex-1 min-w-0">
                    <span class="truncate text-sm font-medium">${chat.title}</span>
                    <span class="text-xs opacity-50">${chat.time}</span>
                </div>
            `;
            
            chatItem.onclick = () => {
                this.showNotification(`Loading ${chat.title}...`, 'info');
            };
            
            chatHistoryContainer.appendChild(chatItem);
        });
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    updateMarketOverview() {
        const marketOverview = document.getElementById('market-overview');
        if (!marketOverview) return;
        
        // Simulate real market data
        const marketData = [
            { name: 'NIFTY 50', value: '22,458.10', change: '+0.85%', positive: true },
            { name: 'BANK NIFTY', value: '48,127.30', change: '-0.42%', positive: false },
            { name: 'SENSEX', value: '74,239.15', change: '+1.12%', positive: true }
        ];
        
        marketOverview.innerHTML = '';
        
        marketData.forEach(item => {
            const marketItem = document.createElement('div');
            marketItem.className = `market-ticker ${item.positive ? '' : 'negative'}`;
            marketItem.innerHTML = `
                <div class="flex justify-between items-center">
                    <div>
                        <div class="text-xs font-medium opacity-80">${item.name}</div>
                        <div class="text-lg font-bold">${item.value}</div>
                    </div>
                    <div class="text-right">
                        <div class="text-sm font-medium ${item.positive ? 'text-success' : 'text-error'}">
                            ${item.change}
                        </div>
                        <i data-lucide="${item.positive ? 'trending-up' : 'trending-down'}" 
                           class="w-4 h-4 ${item.positive ? 'text-success' : 'text-error'}"></i>
                    </div>
                </div>
            `;
            
            marketOverview.appendChild(marketItem);
        });
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    // Cleanup
    cleanup() {
        if (this.socket) {
            this.socket.close(1000, 'Page unload');
        }
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    window.tradingAssistant = new TradingAssistant();
});

// Global functions for backward compatibility and HTML onclick handlers
function startNewChat() {
    window.tradingAssistant?.startNewChat();
}

function clearChat() {
    window.tradingAssistant?.clearChat();
}

function toggleConnection() {
    window.tradingAssistant?.toggleConnection();
}

function quickMessage(message) {
    window.tradingAssistant?.quickMessage(message);
}

function getPortfolio() {
    window.tradingAssistant?.getPortfolio();
}

function getFunds() {
    window.tradingAssistant?.getFunds();
}

function showQuickOrders() {
    window.tradingAssistant?.showNotification('Quick orders panel coming soon!', 'info');
}

function placeQuickOrder() {
    window.tradingAssistant?.showNotification('Quick order placement coming soon!', 'info');
}

function toggleTheme() {
    window.tradingAssistant?.toggleTheme();
}

function showSettings() {
    window.tradingAssistant?.showNotification('Settings panel coming soon!', 'info');
}

function showDashboard() {
    window.tradingAssistant?.showNotification('Dashboard view coming soon!', 'info');
}

function showPortfolio() {
    window.tradingAssistant?.quickMessage('Show detailed portfolio analysis with performance metrics');
}

function showOrders() {
    window.tradingAssistant?.quickMessage('List all my orders with status and details');
}

function showAnalytics() {
    window.tradingAssistant?.showNotification('Analytics dashboard coming soon!', 'info');
}

function voiceInput() {
    window.tradingAssistant?.showNotification('Voice input coming soon!', 'info');
}