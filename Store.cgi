#!/usr/bin/perl -w

use strict;
use lib "/home/hosting_locumtest/usr/local/lib/perl5";
use Mojolicious::Lite;
use DBIx::Custom;
use Validator::Custom;
use utf8;
use v5.10.0;

open (DBCONF,"< app.conf") || die "Error open dbconfig file";
my @appconf=<DBCONF>;
close DBCONF;
chomp @appconf;
our $dbi = DBIx::Custom->connect(
			dsn => $appconf[0],
			user => $appconf[1],
			password => $appconf[2],
			option => {mysql_enable_utf8=>1}
);

$dbi->do('SET NAMES utf8');

get '/checkout' => sub {
	my $self=shift;
	my $cart=$self->session('cart') || undef;
    my @pid = keys %{$cart};
    my $countpid=@pid || 0;
    $self->stash(
		page_title => 'Ваша корзина',
        page_caption => 'Ваша корзина',
		message => 'К сожалению ваша корзина пока пуста :(',
	);
    return $self->render('dummy') if $countpid==0 ;
	
	my $pid=' id=';
    $pid=$pid.join(' or id=',@pid); 
    my $result=$dbi->select(
        table => 'product',
        column => ['id','title','price'],
        where => $pid
    );
    $self->stash(
        cart => $cart,
        products => $result->fetch_hash_all
    );
	$self->render('checkout');
};

post '/checkout' => sub {
	my $self = shift;
	my $cart=$self->session('cart');
    my @pid= keys %{$cart};
    my $countpid=@pid || 0;
    $self->stash(
		message => 'Сожалеем, но ваша корзина пока ещё пуста :(',
		page_title => 'Ваша корзина',
        page_caption => 'Ваша корзина',
	);
    return $self->render('dummy') if $countpid==0 ;

    my $pid=' id=';
    $pid=$pid.join(' or id=',@pid);
    my $result=$dbi->select(
        table => 'product',
        column => ['id','title','price'],
        where => $pid
    );

	my $vc = Validator::Custom->new;
	my $param = $self->req->params->to_hash;
	my $rule = [
		person => {message => 'error'} => [
			'not_blank'
		],
		tel => {message => 'error'} => [
			'not_blank'
		],
		#email => {message => 'error'} => [
		#	'not_blank',{
		#		'regex' => qr/^.*\@.*\...+/
		#	}
		#],
		delivery_type => [
			'defined'
		],
		payment_type => [
			'defined'
		],
	];
	my $vresult = $vc->validate($param,$rule);
	if($vresult->is_ok){
		#Generating sign for order
		my $sign = '';
		my $len = 11 + int(rand(10));
		$sign .= chr(48 + rand(74)) for (1..$len);
		$sign =~ s/\W//g;
		#Create order
		$dbi->insert(
			{
				person => $param->{'person'},
				tel => $param->{'tel'},
				email => $param->{'email'},
				address => $param->{'address'},
				deliveryid => $param->{'delivery_type'},
				paymentid => $param->{'payment_type'},
				orderstatus => 0,
				sysdate => \"NOW()",
				sign => $sign,
			},
			table => 'orders',
		);
		my $orderid = $dbi->select(
							column => 'id',
							table => 'orders',
							where => {sign => $sign},
						)->fetch;
		while(my $ref=$result->fetch_hash){
			$dbi->insert(
				{
					productid => $ref->{'id'},
					title => $ref->{'title'},
					price => $ref->{'price'},
					count => $cart->{$ref->{'id'}},
					orderid => $orderid,
				},
				table => 'item',
			);
		};
		return $self->redirect_to('/thankyou');
	}else{
		$self->stash(
        	cart => $cart,
	        products => $result->fetch_hash_all
	    );
		$self->stash(missing => 1) if $vresult->has_missing;
		$self->stash(messages => $vresult->messages_to_hash) if $vresult->has_invalid;
	}
	$self->render('checkout');
};

get '/thankyou' => sub {
	my $self = shift;
	$self->session(expires => 1);#Clearing cart
	$self->stash(
		page_title => 'Спасибо за заказ',
		page_caption => 'Заказ оформлен',
		message=>'Поздравляем! Ваш заказ оформлен. Наши менеджеры уже им занимаются. Спасибо за доверие.',
	);
	$self->render('dummy');
};

get '/cart' => sub {
    my $self = shift;
    my $cart = $self->session('cart');
	my @pid = keys %{$cart} if $cart;
	my $countpid=@pid || 0;
	$self->stash(
		page_title => 'Ваша корзина',
		page_caption => 'Ваша корзина',
		message => 'Нам очень жаль, но похоже, что ваша корзина пуста :('
	);
	return $self->render('dummy') if $countpid==0 ;

	my $pid=' product.id=';
	$pid=$pid.join(' or product.id=',@pid);	
	my $result=$dbi->select(
		table => 'product',
		column => [
			'product.id',
			'product.title',
			'product.price',
			'product.url',
			'product.caturl',
		],
		where => $pid,
	);
    $self->stash(
		cart => $cart,
		products => $result->fetch_hash_all,
	);
    $self->render('cart');
};

post '/cart' => sub{
    my $self=shift;
    my $productid=$self->param('prodid') || 0;
	my $action=$self->param('action');
    my $cart=$self->session('cart');
	if($action eq 'add'){
	    $cart->{$productid}++;
	}elsif($action eq 'remove'){
		$cart->{$productid}-- if $cart->{$productid}>0;
	}
	if($cart->{$productid}==0 || $action eq 'drop'){
		delete $cart->{$productid};
	}
	$self->session(cart => $cart);
	my @pid= keys %{$cart};
	my $countpid=@pid || 0;
	$self->stash(
        page_title => 'Пустая корзина',
        page_caption => 'Ваша корзина',
        message => 'Мы сожалеем, что вам ничего не понравилось, может пройдётесь по другим разделам нашего магазина?'
    );
    return $self->render('dummy') if $countpid==0 ;

	my $pid=' id=';
    $pid=$pid.join(' or id=',@pid);
    my $result=$dbi->select(
        table => 'product',
        column => [
			'product.id',
			'product.title',
			'product.price',
			'product.caturl',
			'product.url',
		],
        where => $pid
    );
    $self->stash(
		products => $result->fetch_hash_all,
		cart => $cart
	);
    $self->render('cart');
};

get '/catalog/:caturl' => sub {
	my $self = shift;
	my $caturl = $self->param('caturl');
	my $catalog = $dbi->select(
						table => 'catalog',
						column => [
							'catalog.title',
							'catalog.url',
							'catalog.description',
						],
						where => {'catalog.url' => $caturl},
					);
	my $result = $dbi->select(
		table => 'product',
		column => [
			'product.title',
			'product.url',
			'product.anonse',
			'product.instore',
			'product.id',
			'product.price',
			'product.image',
		],
		where => {'product.caturl' => $caturl},
	);
	my $get_data = $catalog->one;
    return $self->render('not_found') if !$get_data;
	$self->stash(
		product => $result->fetch_hash_all,
		catalog => $get_data,
	);
	$self->render('catalog');
};

get '/catalog/:caturl/:produrl' => sub {
	my $self = shift;
	my $caturl = $self->param('caturl');
	my $produrl = $self->param('produrl');
    my $catalog = $dbi->select(
		table => 'catalog',
        column => [
			'catalog.title',
			'catalog.url'
		],
        where => {'catalog.url' => $caturl},
	);
	my $result=$dbi->select(
		table => 'product',
        column => [
			'product.id',
			'product.title',
			'product.price',
			'product.description',
			'product.settings',
			'product.features',
			'product.image',
			'product.instore',
			'product.url',
			'product.image',
		],
		where => {
			'product.url' => $produrl
		},
	);
	my $get_data = $result->fetch_hash;
    return $self->render('not_found') if !$get_data;
	$self->stash(
		product => $get_data,
		catalog => $catalog->one,
	);
	$self->render('product');
};

get '/about/:pageurl' => sub{
	my $self=shift;
	my $pageurl = $self->param('pageurl');
	my $catalog = $dbi->select(
        table => 'catalog',
        column => [
			'catalog.title',
			'catalog.url',
			'catalog.description',
			'catalog.content',
		],
        where => {url => $pageurl},
    );
	my $get_data = $catalog->one || undef;
	return $self->render('not_found') if !$get_data;
	$self->stash(
		catalog => $get_data,
	);
	$self->render('page');
};

get '/' => sub{
	my $self = shift;
	my $catalog = {'url' => 'index'};
	$self->stash(catalog => $catalog);
	$self->render('index');
};

get '/sitemap' => sub{
	my $self = shift;
	my $pages = $dbi->select(
		table => 'catalog',
        column => [
			'url',
			'type',
			'priority',
			'changefreq',
			'lastmod',
		],
	);
	my $products = $dbi->select(
		table => 'product',
		column => [
			'url',
			'caturl',
		],
	);
	$self->stash(
		pages => $pages->fetch_hash_all,
		products => $products->fetch_hash_all,
	);
	$self->render('sitemap');
};

app->secret('ReginaSpector');
app->hook(before_dispatch => sub {
				my $self = shift;
				$self->req->url->base(Mojo::URL->new(q{http://www.nastartshop.ru/}));
			}
		);
app->start;
