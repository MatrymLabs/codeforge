// codeforge-edge: a transparent TCP edge gateway in front of the Python game gateway.
//
// The Python gateway (parts/gateway.py) is thread-per-connection: one OS thread per socket, capped
// (MAX_CONNECTIONS = 128) because that model has a ceiling. This edge accepts the connections in
// Go instead -- one cheap goroutine per direction -- and byte-proxies each straight through to the
// gateway. Telnet/IAC negotiation stays end-to-end (the edge never inspects the stream), so the
// edge is a thin, safe pump that raises the concurrency ceiling without touching game logic.
//
// It is OPTIONAL (ADR-0010 / ADR-0011): when this binary is not built, parts.edge runs the identical
// pure-Python reference proxy and the game is unaffected. Parity + benchmark live in the Python repo.
package main

import (
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"os/signal"
	"sync"
	"syscall"
)

// serveEdge binds listenAddr and proxies every accepted connection to backendAddr. It returns the
// bound listener immediately (so a caller or test can read its address and Close it) and runs the
// accept loop in a background goroutine. Use ":0" for listenAddr to bind an ephemeral port; read
// the real address from the returned listener's Addr().
func serveEdge(listenAddr, backendAddr string) (net.Listener, error) {
	ln, err := net.Listen("tcp", listenAddr)
	if err != nil {
		return nil, err
	}
	go acceptLoop(ln, backendAddr)
	return ln, nil
}

// acceptLoop hands each new connection to its own goroutine until the listener is closed.
func acceptLoop(ln net.Listener, backendAddr string) {
	for {
		client, err := ln.Accept()
		if err != nil {
			return // listener closed: stop cleanly
		}
		go handleConn(client, backendAddr)
	}
}

// handleConn dials the backend for one client and pumps bytes both ways until either side closes.
// If the backend is unreachable, the client is dropped cleanly rather than left hanging.
func handleConn(client net.Conn, backendAddr string) {
	defer client.Close()

	backend, err := net.Dial("tcp", backendAddr)
	if err != nil {
		return // backend down: close the client and move on
	}
	defer backend.Close()

	var wg sync.WaitGroup
	wg.Add(2)
	go pump(&wg, backend, client) // client -> backend
	go pump(&wg, client, backend) // backend -> client
	wg.Wait()
}

// pump copies one direction until src reaches EOF, then half-closes dst's write side so the peer
// sees the close (a one-way shutdown, not a full teardown -- the other direction may still flow).
func pump(wg *sync.WaitGroup, dst, src net.Conn) {
	defer wg.Done()
	io.Copy(dst, src) //nolint:errcheck // a closed peer is the normal end of a proxied stream
	if tcp, ok := dst.(*net.TCPConn); ok {
		tcp.CloseWrite() //nolint:errcheck // best-effort half-close; full Close still runs on return
	}
}

func main() {
	listen := flag.String("listen", ":4001", "address to accept client connections on")
	backend := flag.String("backend", "127.0.0.1:4000", "gateway address to proxy connections to")
	flag.Parse()

	ln, err := serveEdge(*listen, *backend)
	if err != nil {
		log.Fatalf("edge: cannot listen on %s: %v", *listen, err)
	}
	// A machine-readable readiness line on stdout (the bound address, resolved even for :0), so a
	// launcher/test knows exactly where to connect. Humans get the friendly log line on stderr.
	fmt.Printf("READY %s\n", ln.Addr().String())
	log.Printf("edge: listening on %s -> %s", ln.Addr(), *backend)

	// Run until signalled, then close the listener for a clean exit.
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
	ln.Close() //nolint:errcheck // shutting down anyway
}
