# Copy a host-built static binary (CGO_ENABLED=0) so we never pull a golang image onto /.
FROM alpine:3.20
RUN adduser -D -H -u 65532 router
COPY groundwire-router /usr/local/bin/groundwire-router
USER router
EXPOSE 8090
ENTRYPOINT ["/usr/local/bin/groundwire-router"]
