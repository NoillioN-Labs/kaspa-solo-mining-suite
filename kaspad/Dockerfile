FROM suprnational/rusty-kaspa:latest

# Switch to root to perform permission changes
USER root

# Create the data directory and ensure it has open permissions
RUN mkdir -p /app/data && chmod 0777 /app/data

# The default rusty-kaspa image entrypoint runs the node
# We just need to make sure the mounted volume gets the right permissions at runtime.
# So we wrap the entrypoint with a script.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--utxoindex", "--appdir", "/app/data", "--listen=0.0.0.0:16111", "--rpclisten=0.0.0.0:16110", "--rpclisten-json=0.0.0.0:18110"]
