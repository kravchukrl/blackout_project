# Blackout Monitor
The project monitors blackouts/


## Hardware 
- Relay (5V Single-Channel Relay Module)
- USB power cable 
- RasberryPi with GPIO (i.e RPi 4)
- DC UPS for RasberryPi
- Internet connection
```plantuml
@startuml

node "USB receptacle,5V" as usb_port #grey
node "USB plug" as usb #green
usb_port -[#red]-> usb: " +5V"
usb_port -[#blue]-> usb: " -5V" 

node  relay #green[
    <b>Relay</b> 
    <b>VCC</b> Supply input for powering the relay coil
    <b>Ground</b> 0V reference
    <b>Input</b> Input to activate the relay
    <b>Common</b> Common terminal of the relay
    <b>NC</b> Normally closed contact of the relay
]
usb -[#red]-> relay: " + to VCC and  Input"
usb -[#blue]-> relay: " -5V to Ground"


package RPi{
    node gpio [
        <b>GPIO</b>
        pin0: 3V3 power
        GPIO ""x"":Read Pin
    ]  
    node cron
    node "read_pin.py" as read_py
    node "aggregate.py" as aggregate
    
}

gpio -[#orange]-> relay: pin0 to Common
relay -[#orange]-> gpio: NC to GPIO <x>
read_py -- gpio
cron -- read_py 
cron -- aggregate 


package AWS{
    node dynamoDB  [
        <b>Amazon DynamoDB</b>
        ""blackout-monitor-minutes""
        ""blackout-monitor-hours""
        ""blackout-monitor-days""
    ]  
    node s3  [
        <b>Amazon SW</b>
        ""Web App""
    ]  
}
read_py -- dynamoDB
aggregate -- dynamoDB

actor User as user

s3 -- user
dynamoDB -- user
@enduml
```


## Use Case
1. cron triggers GPIO reading every minute. If USB powered - reading is `1` (means `ON`), otherwise `0` (means `OFF`)
2. Reading with device alias, GPIO number and time stamp stored to database
3. cron triggers reading aggregation every hour. It query new readings and re-calculate hourly and daily statistic
4. user getting statistic from aggregated or raw data



```plantuml
@startuml
boundary    "USB 5V" as usb
boundary     Relay    as relay

box RaspberryPi
    boundary    GPIO as gpio
    control     cron
    control     "Read PIN"    as read_pin
    control     "Aggregate Readings"    as aggregation
end box

' entity "Minute Reading" as reading
' entity "Hourly Aggregate" as hourly_aggregate
' entity "Daily Aggregate" as daily_aggregate


box ASW DynamoDB 
    database "blackout-monitor-minutes" as db_mins
    database "blackout-monitor-hours" as db_hours
    database "blackout-monitor-days" as db_days
end box
box AWS S3 
    database "Web UI on S3" as front
end box

control  "Web browser" as chrome  #green
actor User as user #green

group Readings every minute 

    activate relay
    activate gpio
    activate usb

    usb->relay: 5V 
    gpio->relay: 3.3V
    relay-->gpio: 3.3V
 
    activate cron
    cron -> read_pin: Read GPIO 
    deactivate cron
    activate read_pin
    read_pin -> gpio: Read PIN
    gpio --> read_pin: PIN Status

    read_pin -> db_mins: PUT device, pin, timestamp: reading
 

    deactivate read_pin

end


group Aggregation every hour 
    activate cron
    cron -> aggregation: Run aggregation
    deactivate cron
    
    activate   aggregation

    aggregation -> db_mins: query new readings
    db_mins --> aggregation: readings items
    aggregation -> aggregation: aggregate minutes to hours
    aggregation -> db_hours: PUT device, pin, timestamp: on, off, unknown
   
    aggregation -> db_hours: query new hourly statistic
    db_hours --> aggregation: hourly items
    aggregation -> aggregation: aggregate hours to days
    aggregation -> db_days: PUT device, pin, timestamp: on, off, unknown

    deactivate aggregation
end

group User
    activate user
    user -> chrome: Get Statistic

    activate chrome
   
    chrome -> front: Get Web App
    front --> chrome: Web App
    chrome -> db_days: Query Daily Statistic
    db_days --> chrome: Daily Items
    chrome -> db_hours: Query Hourly Statistic
    db_hours --> chrome: Hours Items
    chrome -> db_mins: Query readings
    db_mins --> chrome: Raw Reading Items
    chrome --> user: Statistic on UI

    deactivate chrome
    deactivate user
end
@enduml
```
## Project structure
- `/buffer` - buffer for readings, first they stored on file system then put to the database
- `/cron_example` - example of `cron` confuguration for readings and aggregation
- `/logs` - reading and aggregation daily logs
- `aggregate.py` - hou rly and daily aggregation 
- `dynamo.py` - dynamodb helper
- `read_pin.py` - read  GPIO
- `utils.py` - logging, buffering and other utils
- `requirements_dev.txt` -  development dependencies
- `requirements.txt` - prod dependencies
- `visualise.ipynb` - Jupiter Notebook test visualization

## Amazon Web Services
The project uses [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) as Cloud Storage of readings.

Amazon DynamoDB is a Serverless, NoSQL, fully managed database with single-digit millisecond performance at any scale.

Key reason of using DynamoDB is a very low price and scalability.

DynamoDB designed as Time series, inspired by [Designing Time-Series Data In DynamoDB](https://dev.to/urielbitton/designing-time-series-data-in-dynamodb-kcj)

To optimize reading need to use `Query` operation rather than `Scan` [Best practices for querying and scanning data in DynamoDB
](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-query-scan.html)

To use `Query` operation need send queries using equal condition on `Partition` and `Sort` key (`PK` and `SK`).

Thera are two pairs of `PK` and `SK` query by:
-  device and time range (main `PK` and `SK`)
-  device and aggregation status (`PK` and `SK` in index )

Here is example of `PK` and `SK`:

| Table | `pk` (main)| `sk` (main) | `pk_status` (index) | `ts` |
|--|--|--|--|--|
| `blackout-monitor-minutes` | `device#alex_rpi#sensor#4#date#2025-06-21-19` |`time#00` |`device#alex_rpi#sensor#4#status#done` |`2025-06-21T19:00:03.241969+00:00` |
| `blackout-monitor-hours` | `device#alex_rpi#sensor#4#date#2025-06-25` |`time#00` |`device#alex_rpi#sensor#4#status#done` |`2025-06-25T01:05:04.419859+00:00` |
| `blackout-monitor-days` | `device#temp#sensor#4#date#2025-06` |`time#08` |`device#temp#sensor#4#status#new` |`2025-06-11T17:54:21.718067+00:00` |

```plantuml
@startuml
' hide the spot
' hide circle

' avoid problems with angled crows feet
skinparam linetype ortho

entity "blackout-monitor-minutes" as mins {
  *device : String <<pk>> <<pk_status>>
  *sensor : String <<pk>> <<pk_status>>
  *date: String <<pk>>
  *status: ProcessingStatus <<pk_status>>  
  *time: String <sk>
  *ts : String <<sk_status>>
  --
  *reading: Reading
}
entity "blackout-monitor-hours" as hours {
  *device : String <<pk>> <<pk_status>>
  *sensor : String <<pk>> <<pk_status>>
  *date: String <<pk>>
  *status: ProcessingStatus <<pk_status>>  
  *time: String <sk>
  *ts : String <<sk_status>>
  --
  *count: Number
  *expected: Number
  *off: Number
  *on: Number
  *unknown: Number

}
entity "blackout-monitor-days" as days {
  *device : String <<pk>> <<pk_status>>
  *sensor : String <<pk>> <<pk_status>>
  *date: String <<pk>>
  *status: ProcessingStatus <<pk_status>>  
  *time: String <sk>
  *ts : String <<sk_status>>
  --
  *count: Number
  *expected: Number
  *off: Number
  *on: Number
  *unknown: Number

}
days --> hours
hours --> mins

note bottom of days
  Stores <b>daily</b> aggregated readings calculated from ""blackout-monitor-hours"" 
  <b>Field Notes</b>
  |= field|= description |= example |
  | date | UTC Month, ""YYYY-MM"" | ""2025-08"" |
  | time | UTC Day, ""DD"" | ""02"" |
  | count | Number of raw minutes readings | ""1300"" |
  | expected | Expected minutes readings, always 1440 | ""1440"" |
  | off | OFF readings | ""300"" |
  | on | ON readings | ""1000"" |
  | unknown | Number of missed readings, ""expected=on+off+unknown""  | ""140"" |

  <i>If field description missed refer to ""blackout-monitor-minutes"" doc </i> 

  <b>Partition Key,Sort Key</b>
   <b>pk</b>=""device,sensor,date""
   <b>sk</b>=""time""
  <i>i.e.</i> 
  pk=""device#anton_rpi#sensor#4#date#2025-06-21""
  sk=""time#19""
  
  <b>Index sk_status-index</b>
  <i>The same as ""blackout-monitor-minutes"" doc </i> 

end note
note bottom of hours
  Stores <b>hourly</b> aggregated readings calculated from ""blackout-monitor-minutes"" 
  <b>Field Notes</b>
  |= field|= description |= example |
  | date | UTC Day, ""YYYY-MM-DD"" | ""2025-08-02"" |
  | time | UTC Hour, ""HH"" | ""15"" |
  | count | Number of raw minutes readings | ""54"" |
  | expected | Expected minutes readings, always 60 | ""60"" |
  | off | OFF readings | ""14"" |
  | on | ON readings | ""40"" |
  | unknown | Number of missed readings, ""expected=on+off+unknown""  | ""6"" |

  <i>If field description missed refer to ""blackout-monitor-minutes"" doc </i> 

  <b>Partition Key,Sort Key</b>
   <b>pk</b>=""device,sensor,date""
   <b>sk</b>=""time""
  <i>i.e.</i> 
  pk=""device#anton_rpi#sensor#4#date#2025-06-21""
  sk=""time#19""
  
  <b>Index sk_status-index</b>
  <i>The same as ""blackout-monitor-minutes"" doc </i> 

end note

note bottom of mins
  Stores minutes raw readings from device sensor 
  <b>Field Notes</b>
  |= field|= description |= example |
  | device | Device alias | ""Anton RPi""|
  | sensor | Sensor name (i.e GPIO pin) |""4"" |
  | reading |  On/OFF | ""0"" |
  | date | UTC Hours, ""YYYY-MM-DD-HH"" | ""2025-08-02-15"" |
  | time | UTC Minutes, ""mm"" | ""58"" |
  | ts | Reading timestamp, ISO 8601 | ""2025-08-02T15:58:03.474695+00:00""|

  <b>Partition Key,Sort Key</b>
   <b>pk</b>=""device,sensor,date""
   <b>sk</b>=""time""
  <i>i.e.</i> 
  pk=""device#anton_rpi#sensor#4#date#2025-06-21-19""
  sk=""time#01""
  
  <b>Index sk_status-index</b>
   <b>pk_status</b>="">device,sensor,status""
   <b>ts</b>=""ts""
  <i>i.e.</i> 
  <b>pk_status</b>=""device#alex_rpi#sensor#4#status#done""
  <b>ts</b>=""2025-06-21T19:00:03.241969+00:00""
end note
enum Reading {
  0 : Number
  1 : Number
  -- description --
  0: OFF
  1: ONN
}
enum ProcessingStatus {
  done : String
  new: String
  -- description --
  done: Processed
  new: Not processed yet
}

@enduml
```



## Storage  DynamoDB



# Prerequisites 

## Prequisites RPi
1. Setup python 3.10+
2. Setup AWS CLI https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
3. Authorize to AWS CLI `aws configure` https://docs.aws.amazon.com/cli/latest/userguide/cli-authentication-user.html#cli-authentication-user-configure-wizard
4. Setup python venv  `python -m venv ./.venv` https://docs.python.org/3/library/venv.html
5. Setup packages `./.venv/bin/pip install -r requirements.txt`

## GPIO setup on Raspberry 

```
sudo apt-get update
sudo apt-get -y install python3-rpi.gpio
python -m venv ./.venv
.venv/bin/pip install -r ./requirements.txt
```

## Configure cron
Needed to regular read and aggregate readings

1. Add lines to crontab. Specify your user name instead of `pi`  
```
*  *	* * *	pi	cd / && run-parts --report /etc/cron.minutes.pi
05 *	* * *	pi	cd / && run-parts --report /etc/cron.hourly.pi
```
2. Run  (sudo)
```
mkdir -p /etc/cron.hourly.pi/
mkdir -p /etc/cron.minutes.pi/

cp ./cron_example/cron.hourly.pi/aggregate_blackout_readings /etc/cron.hourly.pi/aggregate_blackout_readings

cp ./cron_example/cron.minutes.pi/blackout-monitor /etc/cron.minutes.pi/blackout-monitor

chmod +X  /etc/cron.hourly.pi/aggregate_blackout_readings
chmod +X  /etc/cron.minutes.pi/blackout-monitor
```

3. Edit Cron Scripts `/etc/cron.minutes.pi/blackout-monitor` and `/etc/cron.hourly.pi/aggregate_blackout_readings`
Specify 
- project path (i.e `/home/pi/dev/blackout/`) 
- device name  (i.e. `alex_rpi` )
- GPIO pin to read  (i.e. `4` ), refer to [Raspberry Pi Pinout](https://pinout.xyz/)

4. check `./log` if they work properly


## Development
1. Setup packages `./.venv/bin/pip install -r requirements_dev.txt`
2. Setup key for GitHub [for example](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent?platform=linux)


