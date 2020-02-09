function create_bar_chart(element_id, name){
    return new Chart(document.getElementById(element_id).getContext('2d'), {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: name,
                data: [],
                backgroundColor: [],
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                yAxes: [{
                    ticks: {
                        beginAtZero: true
                     }
                }]
            }
        }
    }); 
}

function reset_bar_chart(bar_chart){
    bar_chart.data.datasets[0].data = [];
    bar_chart.data.labels = [];
    bar_chart.data.datasets[0].backgroundColor = [];
}

function add_to_bar_chart(bar_chart, label, value, color='rgba(88, 166, 245, 0.2)'){
    bar_chart.data.datasets[0].data.push(value);
    bar_chart.data.labels.push(label);
    bar_chart.data.datasets[0].backgroundColor.push(color)
}

function create_scatter_chart(element_id, name){
    var config1 = new Chart.Scatter(document.getElementById(element_id).getContext('2d'), {
        data: {datasets:[]},
        options: {
            title: {
                display: true,
                text: name
            },
            scales: {
                xAxes: [{
                    type: 'linear',
                    position: 'bottom',
                    ticks: {
                        userCallback: function (tick) {
                            return tick.toString();
                        }
                    },
                    scaleLabel: {
                        labelString: 'Temperature',
                        display: true,
                    }
                    }],
                yAxes: [{
                    type: 'linear',
                    ticks: {
                        userCallback: function (tick) {
                            return tick.toString();
                        }
                    },
                    scaleLabel: {
                        labelString: 'Time',
                        display: true
                    }
                }]
            }
        }
    });
    return config1;
}

function create_scatter_datasets(label, color, data=undefined){
    var scatter_datasets = {
        backgroundColor: color,
        label: label,
        data: []}
    if (data != undefined){
        scatter_datasets.data.push({"y":data.x_value, "x":data.time_t});
    }
    return scatter_datasets; 
}

function add_to_selected_datasets(datasets, destination, data){
    if (datasets.length == 0){
        return false;
    }
    for (i in datasets){
        console.log(datasets)
        if(datasets[i].label == destination){
            datasets[i].data.push({"y":data.x_value, "x":data.time_t});
            return true;
        }
    }
    return false;
}

function sensor_data_to_scatter_datasets(data){
    var return_datasets = []
    for (i in data){
        var label = data[i].node_name+":"+data[i].sensor_id.toString();
        if (add_to_selected_datasets(return_datasets, label, data[i]) == false){
            return_datasets.push(create_scatter_datasets(label, 'rgba(88, 166, 245, 0.2)', data[i]));
        }
    }
    return return_datasets;
}

function add_datasets_to_scatter_chart(chart, datasets){
    chart.data.datasets = datasets;
    chart.update();
}

var app = angular.module('myApp', []);

app.controller('myCtrl', function($scope, $interval) {
    var tempChart = create_bar_chart("tempChart", "temperatures");
    var humiChart = create_bar_chart("humiChart", 'humidity');
    
    $scope.refresh_temperatures = function(){
        $.ajax({
            url: "http://192.168.1.19:4242/sensors/indoor_temp?latests=1;named=1",
            type: 'get',
            dataType: 'json',
            success: function (data) {
                reset_bar_chart(tempChart);
                for (i in data){
                    var value = data[i].x_value;
                    var label = data[i].node_name+":"+data[i].sensor_id.toString()
                    data[i].date = new Date(1000*data[i].time_t);
                    if (value < 16){
                        add_to_bar_chart(tempChart, label, value, color='rgba(88, 166, 245, 0.2)');
                    }
                    else if (value > 28 & value < 35){
                        add_to_bar_chart(tempChart, label, value, color='rgba(250, 209, 7, 0.2)');
                    }
                    else if (value >= 35){
                        add_to_bar_chart(tempChart, label, value, color='rgba(245, 15, 15, 0.2)');
                    }
                    else {
                        add_to_bar_chart(tempChart, label, value, color='rgba(7, 219, 24, 0.2)');
                    }
                }
                tempChart.update();
                //console.log(data);
            }
        });
    };
    $scope.refresh_humidity = function(){
        $.ajax({
            url: "http://192.168.1.19:4242/sensors/indoor_humidity?latests=1;named=1",
            type: 'get',
            dataType: 'json',
            success: function (data) {
                reset_bar_chart(humiChart);
                for (i in data){
                    var value = data[i].x_value;
                    var label = data[i].node_name+":"+data[i].sensor_id.toString();
                    data[i].date = new Date(1000*data[i].time_t);
                    add_to_bar_chart(humiChart, label, value)
                }
                humiChart.update();
                //console.log(data);
            }
        });
    };
    $scope.refresh_temperatures();
    $scope.refresh_humidity();
    $interval(function () {
        $scope.refresh_temperatures();
        $scope.refresh_humidity();
    }, 10000);
  
});

app.controller('test', function($scope) {
    console.log("test");
    var testChart = create_scatter_chart("testChart", "temperatures");
  
     
    $scope.refresh_humidity = function(){
        $.ajax({
            url: "http://192.168.1.19:4242/sensors/indoor_temp?limit=100000;named=1",
            type: 'get',
            dataType: 'json',
            success: function (data) {
                var datasets = sensor_data_to_scatter_datasets(data);
                add_datasets_to_scatter_chart(testChart, datasets);
                testChart.update();
                console.log(data);
            }
        });
    };
   
    $scope.refresh_humidity();
   
  
});


//testing things

