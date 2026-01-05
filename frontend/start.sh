#!/bin/sh

# Use PORT from environment or default to 80
PORT=${PORT:-80}

# Generate nginx config with correct port
cat > /etc/nginx/conf.d/default.conf << EOF
server {
    listen ${PORT};
    root /usr/share/nginx/html;
    index index.html;
    
    location / {
        try_files \$uri \$uri/ /index.html;
    }
    
    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
}
EOF

echo "Starting nginx on port ${PORT}"
nginx -g "daemon off;"
