import pymongo

#mongoconnection = pymongo.Connection('54.227.251.253', 27017)
mongoconnection = pymongo.Connection('ec2-54-227-251-253.compute-1.amazonaws.com', 27017)
mongodb = mongoconnection.arb
