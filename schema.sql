-- Tabela użytkowników
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela subskrypcji
CREATE TABLE subscriptions (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    plan_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela serwerów
CREATE TABLE servers (
    server_id BIGINT PRIMARY KEY,
    server_name VARCHAR(255) NOT NULL,
    owner_id BIGINT REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settings JSONB DEFAULT '{}'::jsonb
);

-- Tabela statystyk
CREATE TABLE statistics (
    id SERIAL PRIMARY KEY,
    server_id BIGINT REFERENCES servers(server_id),
    user_id BIGINT REFERENCES users(user_id),
    songs_played INTEGER DEFAULT 0,
    play_time INTEGER DEFAULT 0,
    date DATE DEFAULT CURRENT_DATE,
    UNIQUE(server_id, user_id, date)
);

-- Tabela playlist
CREATE TABLE playlists (
    id SERIAL PRIMARY KEY,
    server_id BIGINT REFERENCES servers(server_id),
    name VARCHAR(255) NOT NULL,
    created_by BIGINT REFERENCES users(user_id),
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(server_id, name)
);

-- Tabela utworów w playlistach
CREATE TABLE playlist_songs (
    playlist_id INTEGER REFERENCES playlists(id),
    song_url VARCHAR(255) NOT NULL,
    song_title VARCHAR(255) NOT NULL,
    added_by BIGINT REFERENCES users(user_id),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    position INTEGER NOT NULL,
    PRIMARY KEY (playlist_id, position)
);

-- Indeksy
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_statistics_date ON statistics(date);
CREATE INDEX idx_playlists_server ON playlists(server_id);
CREATE INDEX idx_playlist_songs_playlist ON playlist_songs(playlist_id); 