
/*---------------------------------------------------------------------------------------------
*  Copyright (c) Microsoft Corporation. All rights reserved.
*  Licensed under the MIT License. See License.txt in the project root for license information.
*--------------------------------------------------------------------------------------------*/
//@author: Babak Naderi


// JND setup: Adaptive staircase: 3AFC, 2 down- 1 up: targets 70.7% levelA
var config ={
    jndMaxQuestions:45, // maximum number of questions
    snrStart:1, // SNR 5dB  best quality
    snrEnd :21, // SNR -15dB worse quality
    finishIfReversalIs:7, // use 7 as recommended by Levit t , H. (1992).
    exportFileName:"export.csv",
    testStartAtSNR:10, // The first question will have snr of testStartAtSNR, to start at beginning put 1
	lang: "en", // language could be "de" or "en"
    debug:true
}

function forceNoSpaceInInput(){
    $(".nospace").on({
          keydown: function(e) {
            if (e.which === 32)
              return false;
          },
          change: function() {
            this.value = this.value.replace(/\s/g, "");
          }
        });
}


// array of LogEntry
var logs=[];


// JND setup
//var index=0;
var currentQuestionNum=1;
var successAnsPerSNRLevel=new Array(config.snrEnd-config.snrStart+1).fill(0);
var questionAskedPerSNRLevel=new Array(config.snrEnd-config.snrStart+1).fill(0);
var currentSNRIndex = config.testStartAtSNR - config.snrStart ; // first item of array refers to SNR= config.testStartAtSNR
var correctAnsInCurrentSNRIndex = 0; // number of time that current snr level was answered correctly in a row

var pick_is_added=false;

// logs when reversal happens
var reversalAtSNR =new Array(config.finishIfReversalIs).fill(0);
var reversalAtSNRIndex = 0;
// current direction
var direction =+1



var fileName= "assets/"+config.lang+"_num_snr/{0}S_{1}.wav";

var nums= ["024","093","135","156","246","282","286","289","340","359","401","468","534","591","626","628","680","802","815","913","962"];

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

$( document ).ready(function() {
    // disable logs if not debug
    if (!config.debug)
        console.log = function() {};
});

 // when one audio start to play, pause the all the other ones.
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
          convertedSNR= (6-targetSNrLevel);
         result += "Targeted SNR"+ columnDelimiter + targetSNrLevel + columnDelimiter +"i.e. : "+convertedSNR+ lineDelimiter;
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

	currentSNRIndex= config.testStartAtSNR - config.snrStart;
	correctAnsInCurrentSNRIndex =0;

	addJNDQuestion(currentQuestionNum, config.testStartAtSNR)
	questionAskedPerSNRLevel[currentSNRIndex] ++;
	currentQuestionNum++;
}

var last_num="";
function addJNDQuestion(n,snrLevel){
    pick_is_added = false ;
    // 0: question Number, 1: clip, 2: correct ans
	var template='<fieldset id="fieldset_{0}"><label>{0}.&nbsp;Listen to the following clip and enter the three numbers that you have understood.</label><div class="row" style="margin-top:10px;"> <div align="center">  <audio controls preload="auto" loop id ="audio_{0}"> <source src="{1}" type="audio/wav"></audio> </div> <div align="center"> <input type="text" id="num_{0}" name="num_{0}" required="" class="nospace" autocomplete="off"> </div> <div align="center" style="margin-top:20px"> 	<button type="button" class="btn btn-primary" id="bt{0}" onclick="submitAnsJnd({0},{2},\'{3}\');" >Next</button></div></div></fieldset>';

    a = snrLevel;
    b = config.snrEnd;

	//randomly change the order

    do {
        num = nums[Math.floor(Math.random()* nums.length)];
    } while (num ==last_num);
    last_num = num;
	f=fileName.f(snrLevel,num);

	text = template.f(n,f,snrLevel, num);
	console.log("Question "+n+", : num: "+num, 'f:'+f);

	$("#cmp-body").append(text);
	if ((n-1)>0)
		$("#fieldset_"+(n-1).toString()).prop("disabled", true);
	$('html, body').animate({
		scrollTop: ($('#bt'+n).offset().top)
	},500);
	// avoid space in input
    $(".nospace").on({
      keydown: function(e) {
        if (e.which === 32)
          return false;
        if (e.which === 13){
            $("#bt{0}".f(n)).click();
            return true;
         }
      },
      change: function() {
        this.value = this.value.replace(/\s/g, "");
      }
    });
    setTimeout(function() {document.getElementById("audio_{0}".f(n)).play();$("#num_{0}".f(n)).focus();}, 500);

}

/*
Called when user submits an answer for a pair comparison by clicking on "Next"
*/
function submitAnsJnd(qNum,snr, correct_num){
	if (!document.querySelector('input[name="num_'+qNum+'"]').value){
		alert("Please enter the number you heard.");
		return;
	}
	//disable next button
	$('#bt'+qNum).prop("disabled", true);
	// stop audio playing
	$("audio").each(function(index, audio) {
			audio.pause();
		});
    $("#fieldset_"+(qNum).toString()).prop("disabled", true);

	ans=document.querySelector('input[name="num_'+qNum+'"]').value;

	isCorrect=false;
	console.log("answer:"+ans);
	if (ans == correct_num)
		isCorrect=true;

	entry= new LogEntryJND(qNum,snr,ans,correct_num,isCorrect);
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

	console.log ("currentSNRIndex: "+currentSNRIndex);
	console.log ("correctAnsInCurrentSNRIndex: "+correctAnsInCurrentSNRIndex);

	console.log ("successAnsPerSNRLevel: "+successAnsPerSNRLevel);
	console.log ("questionAskedPerSNRLevel: "+questionAskedPerSNRLevel);


	getNextQuestion();
}

function getNextQuestion(){
    /* check if enough data are collected:
     1. should not ask more than config.jndMaxQuestions questions.
     2. "it is recommended that test-ing continue for at least seven reversals, and that the last six reversals be used
     in obtaining the estimate." [Levit t , H. (1992)]
     */
	if (currentQuestionNum<=config.jndMaxQuestions &&
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
	    // if maximum number of questions achieved, store the last SNR as well,
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
	exFileName=name+"_jnd_d3t.csv";
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
		console.log("n :"+logEntry.questionNumber+", SNR:"+logEntry.SNR+", user_input:"+logEntry.user_input+", correct_input:"+logEntry.correct_input+", isCorrect:"+logEntry.isCorrect);

}

function LogEntryJND(n,snr,ans,correct_ans,isCorrect){
	this.questionNumber=n;
	this.SNR=snr;
	this.user_input=ans;
	this.correct_input=correct_ans;
	this.isCorrect=isCorrect;
	var d = new Date();
	this.t=d.getTime();
}




