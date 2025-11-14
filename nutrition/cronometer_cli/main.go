package main

import (
	"context"
	"encoding/csv"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/jrmycanady/gocronometer"
)

// DailyNutrition represents a single day's nutrition data
type DailyNutrition struct {
	Date     string  `json:"date"`
	Calories float64 `json:"calories"`
	Fat      float64 `json:"fat"`
	Carbs    float64 `json:"carbs"`
	Protein  float64 `json:"protein"`
}

func main() {
	// Parse command line flags
	username := flag.String("username", "", "Cronometer username")
	password := flag.String("password", "", "Cronometer password")
	startDate := flag.String("start", "", "Start date (YYYY-MM-DD)")
	endDate := flag.String("end", "", "End date (YYYY-MM-DD)")
	flag.Parse()

	// Validate required arguments
	if *username == "" || *password == "" {
		fmt.Fprintln(os.Stderr, "Error: username and password are required")
		flag.Usage()
		os.Exit(1)
	}

	// Set default dates if not provided
	var start, end time.Time
	var err error

	if *startDate == "" {
		// Default to 30 days ago
		start = time.Now().AddDate(0, 0, -30)
	} else {
		start, err = time.Parse("2006-01-02", *startDate)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error parsing start date: %v\n", err)
			os.Exit(1)
		}
	}

	if *endDate == "" {
		// Default to today
		end = time.Now()
	} else {
		end, err = time.Parse("2006-01-02", *endDate)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error parsing end date: %v\n", err)
			os.Exit(1)
		}
	}

	// Create context
	ctx := context.Background()

	// Create client and login to Cronometer
	client := gocronometer.NewClient(nil)
	err = client.Login(ctx, *username, *password)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error logging in to Cronometer: %v\n", err)
		os.Exit(1)
	}

	// Export daily nutrition data
	csvData, err := client.ExportDailyNutrition(ctx, start, end)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error exporting nutrition data: %v\n", err)
		os.Exit(1)
	}

	// Parse CSV data
	dailyNutrition, err := parseDailyNutrition(csvData)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing nutrition data: %v\n", err)
		os.Exit(1)
	}

	// Output as JSON
	jsonData, err := json.MarshalIndent(dailyNutrition, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error converting to JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(jsonData))
}

// parseDailyNutrition parses the CSV export into DailyNutrition structs
func parseDailyNutrition(csvData string) ([]DailyNutrition, error) {
	reader := csv.NewReader(strings.NewReader(csvData))
	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("failed to parse CSV: %v", err)
	}

	if len(records) < 2 {
		return []DailyNutrition{}, nil // No data
	}

	// Find column indexes
	header := records[0]
	dateIdx := findColumn(header, "Day")
	caloriesIdx := findColumn(header, "Energy (kcal)")
	fatIdx := findColumn(header, "Fat (g)")
	carbsIdx := findColumn(header, "Carbs (g)")
	proteinIdx := findColumn(header, "Protein (g)")

	if dateIdx == -1 || caloriesIdx == -1 || fatIdx == -1 || carbsIdx == -1 || proteinIdx == -1 {
		return nil, fmt.Errorf("missing required columns in CSV export")
	}

	// Parse each record
	var results []DailyNutrition
	for _, record := range records[1:] {
		if len(record) <= max(dateIdx, caloriesIdx, fatIdx, carbsIdx, proteinIdx) {
			continue // Skip invalid rows
		}

		// Parse numeric values
		calories := parseFloat(record[caloriesIdx])
		fat := parseFloat(record[fatIdx])
		carbs := parseFloat(record[carbsIdx])
		protein := parseFloat(record[proteinIdx])

		// Only include days with actual data
		if calories > 0 || fat > 0 || carbs > 0 || protein > 0 {
			results = append(results, DailyNutrition{
				Date:     record[dateIdx],
				Calories: calories,
				Fat:      fat,
				Carbs:    carbs,
				Protein:  protein,
			})
		}
	}

	return results, nil
}

// findColumn finds the index of a column by name (case-insensitive)
func findColumn(header []string, name string) int {
	nameLower := strings.ToLower(name)
	for i, col := range header {
		if strings.ToLower(col) == nameLower {
			return i
		}
	}
	return -1
}

// parseFloat safely parses a string to float64
func parseFloat(s string) float64 {
	s = strings.TrimSpace(s)
	if s == "" || s == "-" {
		return 0
	}
	val, _ := strconv.ParseFloat(s, 64)
	return val
}

// max returns the maximum of integers
func max(nums ...int) int {
	m := nums[0]
	for _, n := range nums[1:] {
		if n > m {
			m = n
		}
	}
	return m
}
