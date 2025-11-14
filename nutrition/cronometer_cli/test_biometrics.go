package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/jrmycanady/gocronometer"
)

func main() {
	username := flag.String("username", "", "Cronometer username")
	password := flag.String("password", "", "Cronometer password")
	flag.Parse()

	if *username == "" || *password == "" {
		fmt.Fprintln(os.Stderr, "Error: username and password are required")
		os.Exit(1)
	}

	ctx := context.Background()
	client := gocronometer.NewClient(nil)
	
	err := client.Login(ctx, *username, *password)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error logging in: %v\n", err)
		os.Exit(1)
	}

	// Export last 7 days of biometrics
	start := time.Now().AddDate(0, 0, -7)
	end := time.Now()
	
	csvData, err := client.ExportBiometrics(ctx, start, end)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error exporting biometrics: %v\n", err)
		os.Exit(1)
	}

	// Print the CSV to see what columns are available
	fmt.Println(csvData)
}
