package mqtt_client

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"os"
	"strings"
	"sync"
	"syscall"
	"time"

	"data_pipe/internal/config"
	"data_pipe/internal/database"
	"data_pipe/internal/logging"

	"github.com/eclipse/paho.golang/autopaho"
	"github.com/eclipse/paho.golang/paho"
	"github.com/golang-jwt/jwt/v5"
)

const (
	subscribeTimeout      = 10 * time.Second
	subscribeRetryMin     = time.Second
	sessionExpirySeconds  = 24 * 60 * 60
	defaultKeepAliveSecs  = 60
	reconnectBackoffDelay = 5 * time.Second
	// Same paths as FileLock.MQTT_RUN and FileLock.MQTT_SUBSCRIBE.
	// A held subscribe lock means a live backend worker is past EMQX
	// setup. A held run lock means that setup is still rewriting hooks.
	mqttRunLock       = "tmp/mqtt_run_lock.lock"
	mqttSubscribeLock = "tmp/mqtt_subscribe.lock"
)

type SubscribeOptions struct {
	Topic string
	QoS   byte
}

type ClientOption func(*MQTTClient)

func WithReconnectInterval(interval time.Duration) ClientOption {
	return func(c *MQTTClient) {}
}

type MQTTClient struct {
	cfg            *config.Config
	cm             *autopaho.ConnectionManager
	router         *paho.StandardRouter
	messageHandler func(topic string, payload []byte)
	connMu         sync.RWMutex
	ctx            context.Context
	cancel         context.CancelFunc
	wg             sync.WaitGroup
	connected      bool
	// connGen increments on every successful broker connection.
	// Subscribe retries are bound to a generation so a stale disconnect
	// callback cannot abort resubscribe on the live connection.
	connGen     uint64
	connectOnce sync.Once
	postgresDB  *database.PostgresDB
	loadConfigs func(ctx context.Context) error
}

func New(cfg *config.Config, messageHandler func(topic string, payload []byte), postgresDB *database.PostgresDB, loadConfigs func(ctx context.Context) error) (*MQTTClient, error) {
	if cfg == nil {
		return nil, errors.New("config cannot be nil")
	}

	if messageHandler == nil {
		return nil, errors.New("message handler cannot be nil")
	}

	ctx, cancel := context.WithCancel(context.Background())

	client := &MQTTClient{
		cfg:            cfg,
		router:         paho.NewStandardRouter(),
		messageHandler: messageHandler,
		ctx:            ctx,
		cancel:         cancel,
		postgresDB:     postgresDB,
		loadConfigs:    loadConfigs,
	}

	return client, nil
}

func (c *MQTTClient) Connect() error {
	var connectErr error
	c.connectOnce.Do(func() {
		token, err := generateToken(c.cfg)
		if err != nil {
			connectErr = fmt.Errorf("failed to generate token: %w", err)
			return
		}

		mqttURL := fmt.Sprintf(
			"mqtt://%s:%d",
			c.cfg.MQTTHost,
			c.cfg.MQTTPort,
		)

		serverURL, err := url.Parse(mqttURL)
		if err != nil {
			connectErr = fmt.Errorf("failed to parse MQTT URL: %w", err)
			return
		}

		keepAlive := uint16(c.cfg.MQTTKeepAlive)
		if keepAlive == 0 {
			keepAlive = defaultKeepAliveSecs
		}

		cliCfg := autopaho.ClientConfig{
			ServerUrls:                    []*url.URL{serverURL},
			KeepAlive:                     keepAlive,
			CleanStartOnInitialConnection: true,
			// Keep the MQTT session on the broker across brief outages so
			// subscriptions survive even if a SUBSCRIBE after reconnect is delayed.
			SessionExpiryInterval: sessionExpirySeconds,
			ReconnectBackoff:      autopaho.NewConstantBackoff(reconnectBackoffDelay),
			ConnectTimeout:        subscribeTimeout,
			OnConnectionUp: func(cm *autopaho.ConnectionManager, connAck *paho.Connack) {
				// Reconnection is owned by autopaho. This callback is the only
				// safe place to (re)subscribe: SessionPresent may be false after
				// a broker restart, so SUBSCRIBE is always sent.
				gen := c.markConnected()
				if connAck != nil && connAck.SessionPresent {
					logging.Infof("MQTT connection up at %s:%d (session present, generation %d)", c.cfg.MQTTHost, c.cfg.MQTTPort, gen)
				} else {
					logging.Infof("MQTT connection up at %s:%d (new session, generation %d)", c.cfg.MQTTHost, c.cfg.MQTTPort, gen)
				}

				// SUBSCRIBE runs in the background. A rejected or timed out
				// attempt closes this connection so the next one is clean.
				c.startSubscribeRetry(cm, gen)
			},
			OnConnectError: func(err error) {
				logging.Warningf("MQTT connection error: %v", err)
				c.markDisconnected()
			},
			ClientConfig: paho.ClientConfig{
				ClientID: c.cfg.Domain,
				Router:   c.router,
				OnClientError: func(err error) {
					logging.Warningf("MQTT client error: %v", err)
					c.markDisconnected()
				},
				OnServerDisconnect: func(disconnect *paho.Disconnect) {
					logging.Warningf("MQTT server disconnected: %v", disconnect)
					c.markDisconnected()
				},
			},
			ConnectUsername: token,
		}

		c.router.RegisterHandler("#", func(p *paho.Publish) {
			c.messageHandler(p.Topic, p.Payload)
		})

		cm, err := autopaho.NewConnection(c.ctx, cliCfg)
		if err != nil {
			connectErr = fmt.Errorf("failed to create connection manager: %w", err)
			return
		}

		c.connMu.Lock()
		c.cm = cm
		c.connMu.Unlock()

		if err := cm.AwaitConnection(c.ctx); err != nil {
			connectErr = fmt.Errorf("failed to wait for connection: %w", err)
			return
		}
	})

	return connectErr
}

func (c *MQTTClient) markConnected() uint64 {
	c.connMu.Lock()
	defer c.connMu.Unlock()
	c.connected = true
	c.connGen++
	return c.connGen
}

func (c *MQTTClient) markDisconnected() {
	c.connMu.Lock()
	c.connected = false
	c.connMu.Unlock()
}

func (c *MQTTClient) currentConnGen() uint64 {
	c.connMu.RLock()
	defer c.connMu.RUnlock()
	return c.connGen
}

func (c *MQTTClient) startSubscribeRetry(cm *autopaho.ConnectionManager, gen uint64) {
	c.wg.Add(1)
	go func() {
		defer c.wg.Done()
		c.subscribeWithRetry(cm, gen)
	}()
}

// subscribeWithRetry subscribes once this connection is allowed to.
// A failed SUBSCRIBE closes the socket. autopaho then opens a new
// session, which drops a broker denial cached on the old connection.
func (c *MQTTClient) subscribeWithRetry(cm *autopaho.ConnectionManager, gen uint64) {
	announcedWait := false

	for {
		if c.subscriptionStopped(gen) {
			return
		}

		ready, err := backendMQTTReady()
		if err != nil {
			logging.Warningf("MQTT backend lock check failed: %v", err)
		} else if !ready {
			if !announcedWait {
				logging.Infof("Waiting for backend MQTT subscribe lock before subscribing to %s", c.subscriptionTopic())
				announcedWait = true
			}
			if !c.sleep(subscribeRetryMin, gen) {
				return
			}
			continue
		}

		if err := c.subscribe(cm); err != nil {
			logging.Warningf("Failed to subscribe, reconnecting MQTT: %v", err)
			if c.currentConnGen() == gen {
				cm.TerminateConnectionForTest()
			}
			return
		}
		return
	}
}

func (c *MQTTClient) subscriptionStopped(gen uint64) bool {
	select {
	case <-c.ctx.Done():
		logging.Infof("Stop subscribe attempts due to context cancellation")
		return true
	default:
	}
	return c.currentConnGen() != gen
}

func (c *MQTTClient) sleep(delay time.Duration, gen uint64) bool {
	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-c.ctx.Done():
		logging.Infof("Stop subscribe attempts due to context cancellation")
		return false
	case <-timer.C:
		return c.currentConnGen() == gen
	}
}

func backendMQTTReady() (bool, error) {
	subscribing, err := lockHeld(mqttSubscribeLock)
	if err != nil || !subscribing {
		return false, err
	}
	starting, err := lockHeld(mqttRunLock)
	if err != nil || starting {
		return false, err
	}
	return true, nil
}

// lockHeld reads /proc/locks. Trying the lock from this process would
// race with the backend's non-blocking acquire and could steal it.
func lockHeld(path string) (bool, error) {
	info, err := os.Stat(path)
	if err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, err
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		return false, fmt.Errorf("cannot read inode of %s", path)
	}
	target := procLockID(stat)

	data, err := os.ReadFile("/proc/locks")
	if err != nil {
		return false, err
	}
	for _, line := range strings.Split(string(data), "\n") {
		fields := strings.Fields(line)
		if len(fields) >= 6 && fields[1] == "FLOCK" && fields[5] == target {
			return true, nil
		}
	}
	return false, nil
}

// procLockID is the device:inode key printed by /proc/locks.
// Stat_t.Dev is a glibc dev_t, not major<<20|minor. Decoding it the
// other way never matches the lock the backend holds.
func procLockID(stat *syscall.Stat_t) string {
	dev := stat.Dev
	major := uint32((dev&0x00000000000fff00)>>8) |
		uint32((dev&0xfffff00000000000)>>32)
	minor := uint32(dev&0xff) |
		uint32((dev&0x00000ffffff00000)>>12)
	return fmt.Sprintf("%02x:%02x:%d", major, minor, stat.Ino)
}

func (c *MQTTClient) subscriptionTopic() string {
	return fmt.Sprintf("%s/+/pepeunit", c.cfg.Domain)
}

func (c *MQTTClient) subscribe(cm *autopaho.ConnectionManager) error {
	if cm == nil {
		return errors.New("mqtt connection manager is not initialized")
	}

	topic := c.subscriptionTopic()
	ctx, cancel := context.WithTimeout(c.ctx, subscribeTimeout)
	defer cancel()

	_, err := cm.Subscribe(ctx, &paho.Subscribe{
		Subscriptions: []paho.SubscribeOptions{
			{
				Topic: topic,
				QoS:   0,
			},
		},
	})
	if err != nil {
		return fmt.Errorf("failed to subscribe to topic %s: %w", topic, err)
	}

	logging.Infof("Success subscribed to topic pattern: %s", topic)
	return nil
}

func (c *MQTTClient) Disconnect() {
	c.cancel()
	c.connMu.RLock()
	cm := c.cm
	c.connMu.RUnlock()
	if cm != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		_ = cm.Disconnect(ctx)
	}
	done := make(chan struct{})
	go func() {
		c.wg.Wait()
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(time.Second):
	}
}

func (c *MQTTClient) Unsubscribe(topic string) error {
	ctx, cancel := context.WithTimeout(c.ctx, 5*time.Second)
	defer cancel()

	c.connMu.RLock()
	connected := c.connected
	cm := c.cm
	c.connMu.RUnlock()

	if connected && cm != nil {
		_, err := cm.Unsubscribe(ctx, &paho.Unsubscribe{
			Topics: []string{topic},
		})
		if err != nil {
			return fmt.Errorf("failed to unsubscribe from topic %s: %w", topic, err)
		}
		logging.Infof("Active subscriptions: %d", c.GetSubscriptionCount())
	}

	return nil
}

func generateToken(cfg *config.Config) (string, error) {
	claims := jwt.MapClaims{
		"domain": cfg.Domain,
		"type":   "Backend",
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)

	signedToken, err := token.SignedString([]byte(cfg.SecretKey))
	if err != nil {
		return "", fmt.Errorf("failed to sign token: %v", err)
	}

	return signedToken, nil
}

func (c *MQTTClient) GetSubscriptionCount() int {
	return 1 // Since we're subscribing to a single topic
}

func (c *MQTTClient) GetActiveTopics(ctx context.Context) ([]string, error) {
	nodes, err := c.postgresDB.GetActiveUnitIOs(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get active nodes: %w", err)
	}

	topics := make([]string, 0, len(nodes))
	for _, node := range nodes {
		if node.DataPipeYML != nil {
			topic := fmt.Sprintf("%s/%s", c.cfg.Domain, node.UUID)
			topics = append(topics, topic)
		}
	}

	return topics, nil
}
