<?php
$input=file_get_contents("php://stdin");
$infile=tempnam(sys_get_temp_dir(),"");
file_put_contents($infile,$input);
#file_put_contents("log.txt",var_export($argv,true)."\n".$input."\n\n\n",FILE_APPEND);
shell_exec("python mb.py ".$argv[1]." ".$argv[2]." ".$argv[3]." <".escapeshellarg($infile)." >> stdout.txt 2>> stderr.txt");
?>
