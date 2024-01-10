<?php

enum State
{
	case Init;
	case Waiting_Auth;
	case Auth;
	case Waiting_Auth_CC;
	case Auth_CC;
}

enum MessageType
{
	case Register_Request;
	case Register_Reply;
	case Auth_Request;
	case Auth_Reply;
}

$transitions=[
	[
		'from_state'=>State::Init,
		'to_state'=>State::Waiting_Auth,
		'messageType'=>MessageType::Auth_Request,
		'verify'=>function($message)
		{
		}
	]
];
$messages=[
	[
		'type'=>MessageType::Auth_Request,
		'match'=>function($method,$uri,$headers,$body)
		{
			return $method=="POST"&&str_starts_with($uri,"/function/product-purchase-1-authenticate");
		},
		'parse'=>function($method,$uri,$headers,$body)
		{
			return ['user'=>$body['user']];
		}
	]
];
$state=State::Init;
$input=file_get_contents("php://stdin");
list($header,$body)=explode($input,"\r\n\r\n",2);
$tmp=explode($header,"\n");
$req=array_shift($tmp);
if(!preg_match("/(GET|POST|HEAD|PUT|DELETE) ([^ ]+) HTTP\/(\d+(\.\d+))/",$req,$match))
{
	return false;
}
list($_,$method,$uri,$httpVersion)=$match;
$headers=array_merge(...array_map(fn($h) => [explode(":",$h)[0]=>explode(":",$h,2)[1]],$tmp));
foreach($messages as $message)
{
	if($message['match']($method,$uri,$headers,$body))
	{
		$messageType=$message['type'];
		$messageObject=$message['parse']($method,$uri,$headers,$body);
		break;
	}
}
if(!isset($messageType))
{
	return false;
}
foreach($transitions as $transition)
{
	if($transition['from_state']==$state&&$transition['messageType']==$messageType&&$transition['verify']()){}
}
?>