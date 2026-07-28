// Tests for the Go edge proxy: bytes round-trip both directions, many connections run concurrently,
// and an unreachable backend drops the client cleanly instead of hanging. Standard-library `go test`.
package main

import (
	"bufio"
	"fmt"
	"net"
	"sync"
	"testing"
	"time"
)

// echoBackend is a tiny line server that echoes each line back prefixed with "echo:", so a test can
// prove a byte travelled client -> edge -> backend and the reply travelled all the way back.
func echoBackend(t *testing.T) (addr string, stop func()) {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("backend listen: %v", err)
	}
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			go func(c net.Conn) {
				defer c.Close()
				s := bufio.NewScanner(c)
				for s.Scan() {
					fmt.Fprintf(c, "echo:%s\n", s.Text())
				}
			}(c)
		}
	}()
	return ln.Addr().String(), func() { ln.Close() }
}

func TestProxyRoundTripsBothDirections(t *testing.T) {
	backend, stop := echoBackend(t)
	defer stop()
	ln, err := serveEdge("127.0.0.1:0", backend)
	if err != nil {
		t.Fatalf("serveEdge: %v", err)
	}
	defer ln.Close()

	c, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatalf("dial edge: %v", err)
	}
	defer c.Close()

	fmt.Fprint(c, "hello\n")
	got, err := bufio.NewReader(c).ReadString('\n')
	if err != nil {
		t.Fatalf("read reply: %v", err)
	}
	if got != "echo:hello\n" {
		t.Fatalf("round-trip: got %q want %q", got, "echo:hello\n")
	}
}

func TestProxyHandlesManyConcurrentConnections(t *testing.T) {
	backend, stop := echoBackend(t)
	defer stop()
	ln, err := serveEdge("127.0.0.1:0", backend)
	if err != nil {
		t.Fatalf("serveEdge: %v", err)
	}
	defer ln.Close()

	const n = 200 // well past the Python gateway's 128-thread ceiling; goroutines shrug
	var wg sync.WaitGroup
	errs := make(chan error, n)
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			c, err := net.Dial("tcp", ln.Addr().String())
			if err != nil {
				errs <- fmt.Errorf("conn %d dial: %w", i, err)
				return
			}
			defer c.Close()
			msg := fmt.Sprintf("c%d\n", i)
			fmt.Fprint(c, msg)
			got, err := bufio.NewReader(c).ReadString('\n')
			if err != nil {
				errs <- fmt.Errorf("conn %d read: %w", i, err)
				return
			}
			if want := "echo:" + msg; got != want {
				errs <- fmt.Errorf("conn %d: got %q want %q", i, got, want)
			}
		}(i)
	}
	wg.Wait()
	close(errs)
	for e := range errs {
		t.Error(e)
	}
}

func TestProxyDropsClientWhenBackendUnreachable(t *testing.T) {
	// Port 1 refuses: the edge should accept the client then close it, not leave it hanging.
	ln, err := serveEdge("127.0.0.1:0", "127.0.0.1:1")
	if err != nil {
		t.Fatalf("serveEdge: %v", err)
	}
	defer ln.Close()

	c, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatalf("dial edge: %v", err)
	}
	defer c.Close()

	c.SetReadDeadline(time.Now().Add(2 * time.Second))
	if _, err := c.Read(make([]byte, 1)); err == nil {
		t.Fatal("expected the client to be closed when the backend is unreachable, got data")
	}
}
