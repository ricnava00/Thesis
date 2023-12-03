'use strict';

const { KV_Store } = require('kv-store');
const fs = require('fs');

const constants = {
	TABLE_AUTHENTICATION_NAME: process.env.TABLE_AUTHENTICATION_NAME,
	HOST: process.env.HOST,
	USER: process.env.USER,
	PASS: process.env.PASS,
	DBNAME: process.env.DBNAME
};


module.exports = (event, context, callback) => {
	console.log(event);
	const kv = new KV_Store(constants.HOST, constants.USER, 
		constants.PASS, constants.DBNAME, constants.TABLE_AUTHENTICATION_NAME);
	const result = event.body;

	kv.init()
		.then(() => kv.get(event.body.user))
		.then((res) => {
			if (res) {
				result.registered = 'false';
				result.failureReason = 'User already exists';
				kv.close().then(()=>callback(null, result))
			} else if (!event.body.pass) {
				result.registered = 'false';
				result.failureReason = 'Missing password field';
				kv.close().then(()=>callback(null, result))
			} else {
				kv.put(event.body.user, event.body.pass)
					.then(() => kv.close())
					.then(()=>{
						result.registered = 'true'
						callback(null, result)
					})
			}
		})
		.catch(err => callback(err))
};
