package main

import (
	"log"
	"os"
	"strconv"

	"wuwa/mgt/backend/internal/app"
)

func main() {
	cfg, err := app.LoadConfig(".")
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	svc, err := app.New(cfg)
	if err != nil {
		log.Fatalf("init app: %v", err)
	}
	defer svc.Close()

	port := cfg.Port
	if len(os.Args) > 1 {
		port, err = strconv.Atoi(os.Args[1])
		if err != nil {
			log.Fatalf("invalid port: %v", err)
		}
	}

	if err := svc.Run(port); err != nil {
		log.Fatalf("run server: %v", err)
	}
}
