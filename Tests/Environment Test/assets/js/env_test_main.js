

// JND setup: Adaptive staircase: 3AFC, 2 down- 1 up: targets 70.7% levelA
var config ={
    jndMaxQuestions:45,
    snrStart:30, // SNR-  worse quality
    snrEnd :50, // SNR-  best quality
    finishIfReversalIs:7, // use 7 as recommended by Levit t , H. (1992).
    exportFileName:"export.csv",
    debug:true
}


// array of LogEntry
var logs=[];


// JND setup
//var index=0;
var currentQuestionNum=1;
var successAnsPerSNRLevel=new Array(config.snrEnd-config.snrStart+1).fill(0);
var questionAskedPerSNRLevel=new Array(config.snrEnd-config.snrStart+1).fill(0);
var currentSNRIndex = 0; // first item of array refers to SNR= config.snrStart
var correctAnsInCurrentSNRIndex = 0; // number of time that current snr level was answered correctly in a row

var pick_is_added=false;

// logs when reversal happens
var reversalAtSNR =new Array(config.finishIfReversalIs).fill(0);
var reversalAtSNRIndex = 0;
// current direction
var direction =+1

var fileName= "{0}S_";

var fileNames=[
'assets/jnd_noise/{0}female1.wav',
'assets/jnd_noise/{0}female2.wav',
'assets/jnd_noise/{0}male1.wav',
'assets/jnd_noise/{0}male2.wav'
];

/*
Utility functions
*/
String.prototype.format = String.prototype.f = function() {
    var s = this,
        i = arguments.length;
    while (i--) {
        s = s.replace(new RegExp('\\{' + i + '\\}', 'gm'), arguments[i]);
    }
    return s;
};

String.prototype.toMMSS = function () {
    var sec_num = parseInt(this, 10); // don't forget the second param
    var minutes   = Math.floor(sec_num / 60);
    var seconds = sec_num - (minutes * 60);
    if (minutes < 10) {minutes = "0"+minutes;}
    if (seconds < 10) {seconds = "0"+seconds;}
    return minutes+':'+seconds;
}

$( document ).ready(function() {
    // disable logs if not debug
    if (!config.debug)
        console.log = function() {};

    // when one audio start to play, pause the all the other ones.
	$("audio").on("play", function() {
		$("audio").not(this).each(function(index, audio) {
			audio.pause();
		});
	});
});

//same as above, which one is correct!?
document.addEventListener('play', function(e){
    var audios = document.getElementsByTagName('audio');
    for(var i = 0, len = audios.length; i < len;i++){
        if(audios[i] != e.target){
            audios[i].pause();
        }
    }
}, true);

function isEven(n) {
   return n % 2 == 0;
}


/*
 to store the result in a csv file
*/
function convertLogsToCSV() {
        var result, ctr, keys, columnDelimiter, lineDelimiter, data;
        // data to be exported, Part1: logs -> each step that user took
        data = logs;

        columnDelimiter = ',';
        lineDelimiter = '\n';

        keys = Object.keys(data[0]);

        result = '';
        result += keys.join(columnDelimiter);
        result += lineDelimiter;

        data.forEach(function(item) {
            ctr = 0;
            keys.forEach(function(key) {
                if (ctr > 0) result += columnDelimiter;

                result += item[key];
                ctr++;
            });
            result += lineDelimiter;
        });
         // data to be exported, Part2: summary
         result += lineDelimiter;
         result += lineDelimiter;
          // add reversals
         result += "Targeted SNR"+ columnDelimiter + targetSNrLevel + lineDelimiter;
         result += "Reversals"+ columnDelimiter + reversalAtSNR.join() + lineDelimiter;
         result += lineDelimiter;

         snrs= range(config.snrStart,config.snrEnd);
         result += "SNRs"+ columnDelimiter + snrs.join() + lineDelimiter;
         result += "# of questions asked"+ columnDelimiter + questionAskedPerSNRLevel.join() + lineDelimiter;
         result += "# of Correct Answers"+ columnDelimiter + successAnsPerSNRLevel.join() + lineDelimiter;
         result += "success ration"+ columnDelimiter + ratio(successAnsPerSNRLevel,questionAskedPerSNRLevel).join() + lineDelimiter;

        return result;
    }

function range(start,end){
    let a = new Array(end-start+1)
    for (i = 0; i < a.length; i++) {
        a[i]= start+i
    }
    return a;
}
// return (arrayA./ArraB) .* 100
function ratio(arrayA,arrayB){
    if (arrayA.length!= arrayB.length)
        return;
    let result = new Array(arrayA.length)
    for (i = 0; i < result.length; i++) {
        result[i]= Math.round((arrayA[i]/arrayB[i])*100);
    }
    return result;
}

function downloadCSV() {
        var data, filename, link;
        var csv = convertLogsToCSV();
        if (csv == null) return;

        filename = exFileName || config.exportFileName;

		var blob = new Blob([csv], {type: "text/csv;charset=utf-8;"});

		if (navigator.msSaveBlob)
			{ // IE 10+
				navigator.msSaveBlob(blob, filename)
			}else{
				var link = document.createElement("a");
				if (link.download !== undefined){
				// feature detection, Browsers that support HTML5 download attribute
					var url = URL.createObjectURL(blob);
					link.setAttribute("href", url);
					link.setAttribute("download", filename);
					link.style = "visibility:hidden";
					document.body.appendChild(link);
					link.click();
					document.body.removeChild(link);
				}
			}
}



//var jndCenterIndex = -1;

//reset everything first
function start(){
	$("#volumeSet")[0].pause();
	$("#cmp-body").empty();

	logs=[];
	questionPath=[];
	//index=0;
	currentQuestionNum=1;
    reversalAtSNRIndex = 0;
    direction =+1

	currentSNRIndex= 0;
	correctAnsInCurrentSNRIndex =0;
	correctAnsInCurrentSNRIndex =0;
	addJNDQuestion(currentQuestionNum, config.snrStart)
	questionAskedPerSNRLevel[currentSNRIndex] ++;
	currentQuestionNum++;
}


function addJNDQuestion(n,snrLevel){
    pick_is_added = false ;
	var tempelate='<fieldset id="fieldset_{0}"><label>{0}.&nbsp;Which sample has a better quality compared to the other one?</label><div class="row" style="margin-top:10px;"><div class="col-sm-4"><div align="center"><b>Sample A</b></div><div align="right">  <audio controls preload="auto"> <source src="{1}" type="audio/wav"></audio> </div></div><div class="col-sm-4"></div><div class="col-sm-4"><div align="center"><b>Sample B</b></div><div align="left"> <audio controls preload="auto"> <source src="{2}" type="audio/wav"></audio></div></div></div><div class="row"><div class="col-sm-4"></div><div class="col-sm-5"><div class="radio"><label><input type="radio" name="cmp{0}" required="" value="{3}">Quality of <b>Sample A</b> is better.</label></div><div class="radio"><label><input type="radio" name="cmp{0}" required="" value="-1">Difference is <b>not detectable</b>.</label></div><div class="radio"><label><input type="radio" name="cmp{0}" required="" value="{4}">Quality of <b>Sample B</b> is better.</label></div></div><div class="col-sm-3"></div></div><div class="row text-center" style="margin-top:20px">	<button type="button" class="btn btn-primary" id="bt{0}" onclick="submitAnsJnd({0},{3},{4});" >Next</button></div></fieldset>';
    a = snrLevel;
    b = config.snrEnd;

	//randomly change the order
	if (isEven(Math.floor(Math.random()*100))){
	    tmp=b;b= a; a= tmp;
	}
    // randomly choose one of the speakers
	let index= Math.round(Math.random()*3);

	f1=fileNames[index].f(fileName.f(a));
	f2=fileNames[index].f(fileName.f(b));;

	text=tempelate.f(n,f1,f2,a,b);
	console.log("Question "+n+", : A: "+a+", B: "+b);

	$("#cmp-body").append(text);
	if ((n-1)>0)
		$("#fieldset_"+(n-1).toString()).prop("disabled", true);
	$('html, body').animate({
		scrollTop: ($('#bt'+n).offset().top)
	},500);
}

/*
Called when user submit an answer for a pair comparision by clicking on "Next"
*/
function submitAnsJnd(qNum,aSNR,bSNR){
	if (!document.querySelector('input[name="cmp'+qNum+'"]:checked')){
		alert("Please select your answer.");
		return;
	}
	//disable next button
	$('#bt'+qNum).prop("disabled", true);
	// stop audio playing
	$("audio").each(function(index, audio) {
			audio.pause();
		});

	ans=document.querySelector('input[name="cmp'+qNum+'"]:checked').value;
	selected= parseInt(ans);
	isCorrect=false;
	console.log("selected:"+selected);
	if ((aSNR>=bSNR && selected==aSNR )||(aSNR<=bSNR && selected==bSNR ) || (aSNR==bSNR && selected==-1 ))
		isCorrect=true;

	entry= new LogEntryJND(qNum,aSNR,bSNR,ans, isCorrect);
	printLogEntry(entry);
	logs.push(entry);
	// logic of staircase
	// Adaptive staircase: 3AFC, 2 down- 1 up: targets 70.7%
	if (isCorrect){
	    correctAnsInCurrentSNRIndex ++;
		successAnsPerSNRLevel[currentSNRIndex] ++;

		if (correctAnsInCurrentSNRIndex ==2 ){
		    // previously direction was negative, now it was a positive answer, so it is a reversal
            if (direction==-1){
                reversalAtSNR[reversalAtSNRIndex] = currentSNRIndex + config.snrStart;
                reversalAtSNRIndex ++;
                direction = 1;
                pick_is_added= true;
            }
		    currentSNRIndex ++;
		    correctAnsInCurrentSNRIndex= 0;
		}


	}else{
	    // previously direction was positive, now it was a positive answer, so it is a reversal
		if (direction==1){
		    reversalAtSNR[reversalAtSNRIndex] = currentSNRIndex + config.snrStart;
		    reversalAtSNRIndex ++;
		    direction = -1;
		    pick_is_added = true;
		}
		currentSNRIndex --;
		correctAnsInCurrentSNRIndex =0
	}
	console.log ("reversalAtSNR: "+reversalAtSNR);
	console.log ("reversalAtSNRIndex: "+reversalAtSNRIndex);
	getNextQuestion();
}

function getNextQuestion(){
    /* check if enough data are collected:
     1. should not ask more than config.jndMaxQuestions questions.
     2. "it is recommended that test-ing continue for at least seven reversals, and that the last six reversals be used
     in obtaining the estimate." [Levit t , H. (1992)]
     */
	if (currentQuestionNum<config.jndMaxQuestions &&
	    reversalAtSNRIndex < reversalAtSNR.length){
		nextQuestionSNR=currentSNRIndex + config.snrStart;
		//reached the upper range
		if (nextQuestionSNR>config.snrEnd){
			currentSNRIndex=currentSNRIndex-1;
			// add it as a reversal point
			if (!pick_is_added){
			    reversalAtSNR[reversalAtSNRIndex] = currentSNRIndex + config.snrStart;
                reversalAtSNRIndex ++;
                pick_is_added= true;
               }
		}else if (nextQuestionSNR<config.snrStart){
			currentSNRIndex=currentSNRIndex+1;
			direction = 1;
			// add it as a reversal point
			if (!pick_is_added){
			    reversalAtSNR[reversalAtSNRIndex] = currentSNRIndex + config.snrStart;
                reversalAtSNRIndex ++;
                pick_is_added= true;
                }
		}
		nextQuestionSNR=currentSNRIndex + config.snrStart;
		questionAskedPerSNRLevel[currentSNRIndex] ++;
		addJNDQuestion(currentQuestionNum, nextQuestionSNR);
	}else{
	    // if maximum number of questions achived, store the last SNR as well,
	    if (reversalAtSNRIndex < reversalAtSNR.length){
	        reversalAtSNR[reversalAtSNRIndex] = currentSNRIndex + config.snrStart;
            reversalAtSNRIndex ++;
         }
         finished();
	}

	currentQuestionNum++;
}



var targetSNrLevel=-1;
function finished(){
	name=$('#p_name').val();
	exFileName=name+"_jnd.csv";
	template='<h3> <p>Finished!. Please do not close this window, and inform the test moderator. Thanks for your participation. </p><div class="row" style="margin-top:10px;" align="center">	<a href="#" onclick="downloadCSV();">Download the Results</a></div></h3>';

	console.log("jndSuccessAnsPerQuestion: "+ successAnsPerSNRLevel.toString());
	console.log("questionAsked: "+questionAskedPerSNRLevel.toString());
	console.log("currentSNRIndex: "+currentSNRIndex);

	console.log("reversalAtSNR: "+reversalAtSNR);
	console.log("reversalAtSNRIndex: "+reversalAtSNRIndex);
	targetSNrLevel = config.snrStart;
	if (reversalAtSNRIndex > 0){
	    // do not consider the first reversal
	    useReversals= reversalAtSNR.slice(1,reversalAtSNRIndex);
	    sum = useReversals.reduce(function(a, b) { return a + b; });
	    targetSNrLevel = Math.round(sum /useReversals.length);
	}
	console.log("targetSNrLevel: "+targetSNrLevel);

	$("#cmp-body").append(template);
	$("#finishCheck").val("finished");
}

/*
utils for handling the logs and store data
*/
function printLogEntry(logEntry){
		console.log("n :"+logEntry.questionNumber+", A:"+logEntry.A+", B:"+logEntry.B+", choice:"+logEntry.choice+", isCorrect:"+logEntry.isCorrect);

}

function LogEntryJND(n,cA,cB,choice,isCorrect){
	this.questionNumber=n;
	this.A=cA;
	this.B=cB;
	this.choice=choice;
	this.isCorrect=isCorrect;
	var d = new Date();
	this.t=d.getTime();
}




