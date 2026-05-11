/* cmus-web - Alpine.js application logic */

function cmusApp() {
  return {
    // ── State ──────────────────────────────────────────────
    state: {
      status: 'disconnected',
      title: '',
      artist: '',
      album: '',
      file: '',
      position: 0,
      duration: 0,
      volume: 0,
      shuffle: 'off',
      repeat: 'false',
    },
    statusMessage: '',
    connected: false,
    seeking: false,
    _seekPosition: 0,
    _progressDisplay: 0,
    volumeSeeking: false,
    _volumeDisplay: 0,
    showRemaining: false,
    accentColor: localStorage.getItem('accentColor') || '#e74c3c',
    accentColors: ['#e74c3c', '#3498db', '#2ecc71', '#9b59b6', '#e67e22', '#1abc9c', '#e91e63'],
    _eventSource: null,

    // ── Computed ───────────────────────────────────────────
    get artUrl() {
      return this.state.file ? '/art?t=' + encodeURIComponent(this.state.file) : '';
    },

    get trackMeta() {
      return '';
    },

    get position() {
      return this.seeking ? this._seekPosition : this._progressDisplay;
    },

    get timeRight() {
      if (this.showRemaining) {
        return '-' + this.formatTime(this.state.duration - this.state.position);
      }
      return this.formatTime(this.state.duration);
    },

    get controlsDisabled() {
      return !this.connected
        || this.state.status === 'not_running'
        || this.state.status === 'no_track'
        || this.state.status === 'no_cmus';
    },

    // ── Init ──────────────────────────────────────────────
    init() {
      this.setAccentColor(this.accentColor);
      this._connectSSE();

      // Sync volume slider display when SSE updates arrive (only when user isn't dragging)
      this.$watch('state.volume', (value) => {
        if (!this.volumeSeeking) {
          this._volumeDisplay = value;
        }
      });

      // Sync progress slider display when SSE updates arrive (only when user isn't dragging)
      this.$watch('state.position', (value) => {
        if (!this.seeking) {
          this._progressDisplay = value;
        }
      });

      // Keyboard shortcuts are handled via @keydown.window in the template
    },

    // ── Keyboard shortcuts ─────────────────────────────────
    handleKey(e) {
      // Ignore if user is typing in a text input
      const tag = e.target.tagName;
      if (tag === 'TEXTAREA') return;
      if (tag === 'INPUT' && e.target.type !== 'range') return;

      let handled = true;

      // Volume keys: match on e.key (actual character) to handle +, -, and numpad
      if (e.key === '+' || e.code === 'NumpadAdd') {
        this._volumeDisplay = Math.min(100, this._volumeDisplay + 10);
        this.setVolume(this._volumeDisplay);
      } else if (e.key === '-' || e.code === 'NumpadSubtract') {
        this._volumeDisplay = Math.max(0, this._volumeDisplay - 10);
        this.setVolume(this._volumeDisplay);
      } else {
        switch (e.code) {
          case 'Space':
          case 'KeyC':
            this.togglePlay();
            break;
          case 'ArrowLeft':
            this._sendCommand('seek', this.state.position - 5);
            break;
          case 'ArrowRight':
            this._sendCommand('seek', this.state.position + 5);
            break;
          case 'ArrowUp':
            this._volumeDisplay = Math.min(100, this._volumeDisplay + 10);
            this.setVolume(this._volumeDisplay);
            break;
          case 'ArrowDown':
            this._volumeDisplay = Math.max(0, this._volumeDisplay - 10);
            this.setVolume(this._volumeDisplay);
            break;
          case 'KeyB':
            this.next();
            break;
          case 'KeyZ':
            this.prev();
            break;
          case 'KeyS':
            this.toggleShuffle();
            break;
          case 'KeyR':
            this.toggleRepeat();
            break;
          case 'KeyL':
            this.searchLyrics();
            break;
          default:
            handled = false;
        }
      }

      if (handled) e.preventDefault();
    },

    // ── SSE connection ─────────────────────────────────────
    _connectSSE() {
      const self = this;
      this._eventSource = new EventSource('/sse');

      this._eventSource.addEventListener('state', function (e) {
        const data = JSON.parse(e.data);
        self.state.status = data.status || self.state.status;
        self.state.title = data.title || '';
        self.state.artist = data.artist || '';
        self.state.album = data.album || '';
        self.state.file = data.file || '';
        self.state.position = data.position !== undefined ? data.position : self.state.position;
        self.state.duration = data.duration !== undefined ? data.duration : self.state.duration;
        self.state.volume = data.volume !== undefined ? data.volume : self.state.volume;
        self.state.shuffle = data.shuffle !== undefined ? data.shuffle : self.state.shuffle;
        self.state.repeat = data.repeat !== undefined ? data.repeat : self.state.repeat;

        self.connected = true;

        // Status-specific messages
        if (data.status === 'not_running') {
          self.statusMessage = '⚠ cmus is not running';
        } else if (data.status === 'no_track') {
          self.statusMessage = '♪ No track loaded';
        } else if (data.status === 'no_cmus' || data.status === 'error') {
          self.statusMessage = '⚠ cmus-remote not found';
        } else {
          self.statusMessage = '';
        }
      });

      this._eventSource.onerror = function () {
        self.connected = false;
        self.statusMessage = '⟳ Disconnected - reconnecting...';
      };
    },

    // ── Command methods ────────────────────────────────────
    async _sendCommand(action, value) {
      const url = '/command/' + action;
      const options = { method: 'POST' };
      if (value !== undefined && value !== null) {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify({ value: parseInt(value, 10) });
      }
      try {
        await fetch(url, options);
      } catch (err) {
        console.error('Command failed:', action, err);
      }
    },

    togglePlay() {
      const action = this.state.status === 'playing' ? 'pause' : 'play';
      this._sendCommand(action);
    },

    next() {
      this._sendCommand('next');
    },

    prev() {
      this._sendCommand('prev');
    },

    seek(value) {
      this._progressDisplay = this._seekPosition;
      this._sendCommand('seek', parseInt(value, 10));
      this.seeking = false;
    },

    setVolume(value) {
      this._sendCommand('volume', parseInt(value, 10));
      this.volumeSeeking = false;
    },

    toggleShuffle() {
      this._sendCommand('shuffle');
    },

    toggleRepeat() {
      this._sendCommand('repeat');
    },

    searchLyrics() {
      const title = this.state.title || '';
      const artist = this.state.artist || '';
      if (!title && !artist) return;
      const query = [title, artist].filter(Boolean).join(' - ') + ' lyrics';
      window.open(
        'https://www.startpage.com/sp/search?query=' + encodeURIComponent(query),
        '_blank'
      );
    },

    toggleTimeDisplay() {
      this.showRemaining = !this.showRemaining;
    },

    // ── Utility ────────────────────────────────────────────
    formatTime(seconds) {
      const s = Math.max(0, Math.floor(seconds));
      return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
    },

    // ── Accent color ───────────────────────────────────────
    setAccentColor(color) {
      this.accentColor = color;
      localStorage.setItem('accentColor', color);
      document.documentElement.style.setProperty('--accent', color);
    },
  };
}

// ── Service worker registration ──────────────────────────────────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/sw.js');
}
