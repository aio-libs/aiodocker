FROM golang:1.10-alpine3.7 as builder
COPY app.go /src/app.go
WORKDIR /src
RUN go build -o main .

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /src
COPY --from=builder /src/main .
CMD ["/src/main"]
