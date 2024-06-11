package main

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/aws/aws-lambda-go/lambda"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/ec2"
	"github.com/aws/aws-sdk-go-v2/service/ec2/types"
)

const (
	tagKey    = "Name"
	tagDev    = "dev"
	tagStable = "stable"
	tagProd   = "prod"
)

type InstanceInfo struct {
	ID       string
	PublicIP string
}

func main() {
	lambda.Start(handler)
}

func handler(ctx context.Context) (string, error) {
	logger := log.New(log.Writer(), "INFO: ", log.LstdFlags)

	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		logger.Fatalf("unable to load SDK config, %v", err)
		return "", err
	}

	ec2Client := ec2.NewFromConfig(cfg)

	reservations, err := GetEC2Instances(ctx, ec2Client)
	if err != nil {
		logger.Println("Error retrieving instances:", err)
		return "", err
	}

	var instancesToTerminate []InstanceInfo

	for _, reservation := range reservations {
		for _, instance := range reservation.Instances {
			logger.Printf("Checking instance %s\n", *instance.InstanceId)

			if instance.State != nil && instance.State.Name == types.InstanceStateNameTerminated {
				logger.Printf("Instance %s is already terminated.\n", *instance.InstanceId)
				continue
			}

			tagValue, hasRelevantTag := getRelevantTagValue(instance.Tags, logger)
			if !hasRelevantTag {
				logger.Printf("Instance %s does not have a relevant tag value and will not be terminated.\n", *instance.InstanceId)
				continue
			}

			if tagValue == tagProd {
				logger.Printf("Instance %s is tagged with '%s' and will continue to run.\n", *instance.InstanceId, tagValue)
				continue
			}

			if instance.LaunchTime != nil {
				if time.Since(*instance.LaunchTime).Hours() > 24 {
					logger.Printf("Instance %s has been running for more than 1 day.\n", *instance.InstanceId)
					publicIP := "N/A"
					if instance.PublicIpAddress != nil {
						publicIP = *instance.PublicIpAddress
					}
					logger.Printf("Instance %s has public IP: %s\n", *instance.InstanceId, publicIP)

					if tagValue == tagDev || tagValue == tagStable {
						logger.Printf("Instance %s is tagged with '%s' and will be terminated.\n", *instance.InstanceId, tagValue)
						err := TerminateInstance(ctx, ec2Client, instance, logger)
						if err != nil {
							logger.Println("Error terminating instance:", err)
						} else {
							logger.Printf("Instance %s marked for termination due to running for more than 1 day.\n", *instance.InstanceId)
							instancesToTerminate = append(instancesToTerminate, InstanceInfo{
								ID:       *instance.InstanceId,
								PublicIP: publicIP,
							})
						}
					}
				} else {
					logger.Printf("Instance %s has been running for less than 1 day and will not be terminated.\n", *instance.InstanceId)
				}
			}
		}
	}

	if len(instancesToTerminate) > 0 {
		var output []string
		for _, instance := range instancesToTerminate {
			output = append(output, fmt.Sprintf("Instance ID: %s, Public IP: %s", instance.ID, instance.PublicIP))
		}
		return "Instances to be terminated: " + strings.Join(output, "; "), nil
	}
	return "No instances to be terminated", nil
}

func getRelevantTagValue(tags []types.Tag, logger *log.Logger) (string, bool) {
	logger.Println("Checking instance tags:", tags)
	for _, tag := range tags {
		value := strings.TrimSpace(*tag.Value)
		logger.Printf("Instance tag value: %s\n", value)
		if value == tagDev || value == tagStable || value == tagProd {
			return value, true
		}
	}
	return "", false
}

func GetEC2Instances(ctx context.Context, client *ec2.Client) ([]types.Reservation, error) {
	resp, err := client.DescribeInstances(ctx, &ec2.DescribeInstancesInput{})
	if err != nil {
		return nil, err
	}
	return resp.Reservations, nil
}

func TerminateInstance(ctx context.Context, client *ec2.Client, instance types.Instance, logger *log.Logger) error {
	resp, err := client.TerminateInstances(ctx, &ec2.TerminateInstancesInput{
		InstanceIds: []string{*instance.InstanceId},
	})
	if err != nil {
		logger.Printf("Error terminating instance %s: %v\n", *instance.InstanceId, err)
		return err
	}

	for _, change := range resp.TerminatingInstances {
		logger.Printf("Termination status of instance %s: %s -> %s\n",
			*change.InstanceId, string(change.PreviousState.Name), string(change.CurrentState.Name))
	}

	return nil
}

