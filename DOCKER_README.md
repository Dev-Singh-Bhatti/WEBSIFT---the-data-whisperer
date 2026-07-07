# Docker Setup Guide

Lightweight CPU-only Docker container for the Multi-Platform Review Scraper.

## Quick Start

### Using Docker Compose (Recommended)

1. **Set environment variables** (create `.env` file or export):
```bash
export DATABASE_URL="sqlite:///./app.db"
export REQUESTS_PER_MINUTE=10
```

2. **Build and run**:
```bash
docker-compose up --build
```

3. **Access the app**:
   - Open browser: http://localhost:8501

### Using Docker directly

1. **Build the image**:
```bash
docker build -t myntra-scraper:latest .
```

2. **Run the container**:
```bash
docker run -d \
  --name myntra-scraper \
  -p 8501:8501 \
  -e DATABASE_URL="sqlite:///./app.db" \
  -e REQUESTS_PER_MINUTE=10 \
  --shm-size=2gb \
  myntra-scraper:latest
```

3. **View logs**:
```bash
docker logs -f myntra-scraper
```

## Environment Variables

Configure via `.env` file or docker-compose.yml:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./app.db` | Database URL (SQLite for prototype) |
| `PROXY_ENABLED` | `False` | Enable proxy rotation |
| `PROXY_LIST` | `` | Comma-separated proxy list |
| `MIN_DELAY` | `2` | Minimum delay between requests (seconds) |
| `MAX_DELAY` | `5` | Maximum delay between requests (seconds) |
| `BROWSER_HEADLESS` | `False` | Run browser headless (`True`) or foreground/headed (`False`) |
| `PAGE_LOAD_STRATEGY` | `eager` | Selenium page load strategy (`normal`, `eager`, `none`) |
| `DELAY_SCALE` | `0.5` | Scales all scraper sleeps (lower is faster) |
| `REQUESTS_PER_MINUTE` | `10` | Rate limit (requests per minute) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Volume Mounts

The docker-compose.yml mounts:
- `./logs` → Container logs directory
- `./data.csv` → Scraped data output

## Image Size Optimization

- Uses `python:3.11-slim` base image (~45MB)
- CPU-only PyTorch (no GPU dependencies)
- Multi-layer caching for faster rebuilds
- Removes apt cache after installation

## Troubleshooting

### Chrome/ChromeDriver Issues
If Chrome fails to start, increase shared memory:
```bash
docker run --shm-size=2gb ...
```

### Out of Memory
If the container runs out of memory:
- Reduce `REQUESTS_PER_MINUTE`
- Increase Docker memory limit
- Use smaller batch sizes for scraping

### Model Download
First-time summarization will download BART model (~1.6GB). This is cached in the container.

## Stopping the Container

```bash
# Using docker-compose
docker-compose down

# Using docker directly
docker stop myntra-scraper
docker rm myntra-scraper
```

## Rebuilding

After code changes:
```bash
docker-compose up --build
```

## Production Considerations

1. **Use environment variables** for sensitive data (database URLs, proxies)
2. **Set appropriate rate limits** to avoid IP bans
3. **Monitor logs** for bot detection warnings
4. **Use reverse proxy** (nginx) for production deployment
5. **Enable HTTPS** for production

